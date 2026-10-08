"""Protected local storage for provider credentials that use API keys/PATs.

This deliberately does not scrape browser sessions or import credentials from
other applications. Providers that expose an official account OAuth flow use a
dedicated integration (as ChatGPT does); these providers currently document
API/PAT credentials for third-party programmatic access.
"""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

from backend.paths import get_app_data_dir

PROVIDERS = {
    "claude": {
        "label": "Claude",
        "credential_label": "Anthropic API key",
        "env_var": "ANTHROPIC_API_KEY",
        "hint": "Create an API key in Anthropic Console. Claude subscription sessions are not imported.",
    },
    "cursor": {
        "label": "Cursor",
        "credential_label": "Cursor user API key",
        "env_var": "CURSOR_API_KEY",
        "hint": "Create a User API Key in Cursor Dashboard. Browser CLI sessions remain owned by Cursor.",
    },
    "devin": {
        "label": "Devin",
        "credential_label": "Devin personal access token",
        "env_var": "DEVIN_API_KEY",
        "hint": "Create a personal access token or service-user API key in Devin settings.",
    },
}


class ProviderCredentialError(ValueError):
    pass


class ProviderCredentialStore:
    def __init__(self) -> None:
        self._directory = get_app_data_dir() / "providers"

    def _path(self, provider: str) -> Path:
        if provider not in PROVIDERS:
            raise ProviderCredentialError(f"Unsupported provider: {provider}")
        return self._directory / f"{provider}.json"

    def _ensure_directory(self) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(self._directory, 0o700)

    def save(self, provider: str, secret: str) -> None:
        if not secret.strip():
            raise ProviderCredentialError("Credential cannot be empty.")
        path = self._path(provider)
        self._ensure_directory()
        temp = path.with_suffix(f".tmp-{os.getpid()}-{secrets.token_hex(4)}")
        descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                json.dump({"secret": secret.strip()}, file)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp, path)
            if os.name != "nt":
                os.chmod(path, 0o600)
        finally:
            temp.unlink(missing_ok=True)

    def delete(self, provider: str) -> None:
        self._path(provider).unlink(missing_ok=True)

    def status(self) -> list[dict[str, Any]]:
        return [
            {"id": key, **metadata, "connected": self._path(key).is_file()}
            for key, metadata in PROVIDERS.items()
        ]


provider_credentials = ProviderCredentialStore()
