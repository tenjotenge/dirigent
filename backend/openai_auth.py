"""Local Sign in with ChatGPT support for Dirigent.

Credentials never cross the frontend boundary.  This module implements the
open-source, loopback OAuth + PKCE flow documented by OpenAI and stores each
account separately under the platform-specific Dirigent data directory.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import uuid
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlencode, urlparse

import jwt
import requests

from backend.paths import get_app_data_dir

AUTHORIZE_URL = "https://auth.openai.com/api/accounts/authorize"
TOKEN_URL = "https://auth.openai.com/api/accounts/oauth/token"
JWKS_URL = "https://auth.openai.com/.well-known/jwks.json"
ISSUER = "https://auth.openai.com"
RESOURCE = "https://api.openai.com/v1"
PLAN_SCOPE = "chatgpt.tokens.use.direct"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"


class OpenAIAuthError(RuntimeError):
    """A safe error that can be shown to the local user."""


@dataclass
class PendingSignIn:
    state: str
    nonce: str
    verifier: str
    redirect_uri: str
    server: ThreadingHTTPServer
    status: str = "pending"
    error: Optional[str] = None
    account_email: Optional[str] = None


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


class ChatGPTAuthService:
    """Owns local OAuth attempts and protected ChatGPT account profiles."""

    def __init__(self) -> None:
        self._directory = get_app_data_dir() / "chatgpt"
        self._profiles_path = self._directory / "profiles.json"
        self._host_path = self._directory / "host.json"
        self._pending: Optional[PendingSignIn] = None
        self._lock = threading.Lock()

    def _ensure_directory(self) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(self._directory, 0o700)

    def _read_json(self, path: Path, fallback: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return fallback

    def _write_json_private(self, path: Path, value: Any) -> None:
        self._ensure_directory()
        tmp = path.with_suffix(f".tmp-{os.getpid()}-{secrets.token_hex(4)}")
        descriptor = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                json.dump(value, file, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(tmp, path)
            if os.name != "nt":
                os.chmod(path, 0o600)
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    def _host_id(self) -> str:
        self._ensure_directory()
        saved = self._read_json(self._host_path, {})
        host_id = saved.get("ext_agent_host_id") if isinstance(saved, dict) else None
        if isinstance(host_id, str) and host_id.startswith("urn:uuid:"):
            return host_id
        host_id = f"urn:uuid:{uuid.uuid4()}"
        self._write_json_private(self._host_path, {"ext_agent_host_id": host_id})
        return host_id

    def _profiles(self) -> list[dict[str, Any]]:
        profiles = self._read_json(self._profiles_path, [])
        return profiles if isinstance(profiles, list) else []

    def active_access_token(self) -> str:
        """Return an OAuth token only to backend provider code."""
        for profile in self._profiles():
            if PLAN_SCOPE in profile.get("scopes", []) and profile.get("access_token"):
                return str(profile["access_token"])
        raise OpenAIAuthError("Connect a ChatGPT account with plan usage enabled first.")

    def status(self) -> dict[str, Any]:
        with self._lock:
            pending = self._pending
            profiles = self._profiles()
            return {
                "status": pending.status if pending else "idle",
                "message": pending.error if pending and pending.error else None,
                "connected": [
                    {
                        "id": profile.get("id"),
                        "email": profile.get("email"),
                        "plan_enabled": PLAN_SCOPE in profile.get("scopes", []),
                    }
                    for profile in profiles
                ],
            }

    def start(self) -> dict[str, str]:
        with self._lock:
            if self._pending and self._pending.status == "pending":
                raise OpenAIAuthError("A ChatGPT sign-in is already waiting for browser approval.")

            state = secrets.token_urlsafe(32)
            nonce = secrets.token_urlsafe(32)
            verifier = secrets.token_urlsafe(64)
            challenge = _base64url(hashlib.sha256(verifier.encode("ascii")).digest())
            server = self._start_callback_server()
            port = server.server_address[1]
            redirect_uri = f"http://127.0.0.1:{port}/auth/callback"
            pending = PendingSignIn(state, nonce, verifier, redirect_uri, server)
            self._pending = pending
            threading.Thread(target=server.serve_forever, daemon=True).start()

            query = {
                "client_id": "dynamic_agent_client",
                "agent_name_hint": "Dirigent",
                "ext_agent_host_id": self._host_id(),
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "scope": SCOPES,
                "resource": RESOURCE,
                "state": state,
                "nonce": nonce,
                "code_challenge_method": "S256",
                "code_challenge": challenge,
            }
            url = f"{AUTHORIZE_URL}?{urlencode(query)}"
            webbrowser.open(url)
            return {"status": "pending", "authorization_url": url}

    def _start_callback_server(self) -> ThreadingHTTPServer:
        service = self

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                service._handle_callback(self.path)
                body = b"<html><body><h2>Dirigent sign-in complete</h2><p>You may return to Dirigent.</p></body></html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: Any) -> None:
                return

        return ThreadingHTTPServer(("127.0.0.1", 0), CallbackHandler)

    def _handle_callback(self, path: str) -> None:
        with self._lock:
            pending = self._pending
            if not pending or pending.status != "pending":
                return
            try:
                parsed = urlparse(path)
                if parsed.path != "/auth/callback":
                    raise OpenAIAuthError("Unexpected OAuth callback path.")
                query = parse_qs(parsed.query)
                if query.get("state", [None])[0] != pending.state:
                    raise OpenAIAuthError("ChatGPT sign-in state did not match.")
                if query.get("error"):
                    raise OpenAIAuthError(query.get("error_description", query["error"])[0])
                code = query.get("code", [None])[0]
                client_id = query.get("client_id", [None])[0]
                if not code or not client_id or client_id == "dynamic_agent_client":
                    raise OpenAIAuthError("ChatGPT did not return a completed client registration.")
                token_data = self._exchange_code(pending, code, client_id)
                identity = self._verify_identity(token_data, client_id, pending.nonce)
                scopes = token_data.get("scope", "").split()
                self._save_profile(identity, token_data, client_id, scopes)
                pending.account_email = identity.get("email")
                pending.status = "connected"
            except Exception as exc:  # Preserve only a safe local status.
                pending.status = "failed"
                pending.error = str(exc)
            finally:
                # shutdown() must not run in the callback handler itself: it
                # waits for serve_forever() to return.
                threading.Thread(target=pending.server.shutdown, daemon=True).start()

    @staticmethod
    def _exchange_code(pending: PendingSignIn, code: str, client_id: str) -> dict[str, Any]:
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "code": code,
                "code_verifier": pending.verifier,
                "redirect_uri": pending.redirect_uri,
                "resource": RESOURCE,
            },
            timeout=20,
        )
        if not response.ok:
            raise OpenAIAuthError("ChatGPT token exchange failed; start sign-in again.")
        return response.json()

    @staticmethod
    def _verify_identity(token_data: dict[str, Any], client_id: str, nonce: str) -> dict[str, Any]:
        id_token = token_data.get("id_token")
        if not isinstance(id_token, str):
            raise OpenAIAuthError("ChatGPT did not return an identity token.")
        signing_key = jwt.PyJWKClient(JWKS_URL).get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=[signing_key.algorithm_name],
            audience=client_id,
            issuer=ISSUER,
        )
        if claims.get("nonce") != nonce:
            raise OpenAIAuthError("ChatGPT identity nonce did not match.")
        if not claims.get("sub"):
            raise OpenAIAuthError("ChatGPT identity is missing an account subject.")
        return claims

    def _save_profile(
        self,
        identity: dict[str, Any],
        token_data: dict[str, Any],
        client_id: str,
        scopes: list[str],
    ) -> None:
        profile_id = f"{identity['sub']}:{client_id}"
        profile = {
            "id": profile_id,
            "email": identity.get("email"),
            "subject": identity["sub"],
            "issuer": identity.get("iss", ISSUER),
            "client_id": client_id,
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token"),
            "id_token": token_data["id_token"],
            "token_type": token_data.get("token_type", "Bearer"),
            "expires_in": token_data.get("expires_in"),
            "scopes": scopes,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        profiles = [item for item in self._profiles() if item.get("id") != profile_id]
        profiles.append(profile)
        self._write_json_private(self._profiles_path, profiles)


chatgpt_auth = ChatGPTAuthService()
