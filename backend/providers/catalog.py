"""Capabilities distinguish direct model APIs from autonomous agent APIs."""
from __future__ import annotations

import os
from typing import Any

from backend.openai_auth import chatgpt_auth
from backend.provider_credentials import provider_credentials

PROVIDERS: tuple[dict[str, Any], ...] = (
    {"id": "lmstudio", "label": "LM Studio", "kind": "direct_model",
     "generation_route": True, "note": "Local inference via the existing tool/policy pipeline."},
    {"id": "chatgpt", "label": "ChatGPT", "kind": "direct_model",
     "generation_route": True, "note": "Existing account-connected generation route."},
    {"id": "claude", "label": "Claude API", "kind": "direct_model",
     "generation_route": True, "note": "Anthropic API key; distinct from a Claude subscription."},
    {"id": "cursor", "label": "Cursor Cloud Agents", "kind": "external_agent",
     "generation_route": False, "note": "Session API needs separate run, artifact, and approval handling."},
    {"id": "devin", "label": "Devin", "kind": "external_agent",
     "generation_route": False, "note": "Session API needs organization scope, run polling, and artifact handling."},
    {"id": "openclaw", "label": "OpenClaw Gateway", "kind": "external_agent",
     "generation_route": False, "note": "Gateway may run its own tools outside Dirigent policy; separate trust boundary."},
)


def provider_capabilities() -> list[dict[str, Any]]:
    credentials = {item["id"]: item["connected"] for item in provider_credentials.status()}
    chatgpt = chatgpt_auth.status()
    configured = {
        "lmstudio": True,
        "chatgpt": chatgpt.get("status") == "connected",
        "claude": credentials["claude"],
        "cursor": credentials["cursor"],
        "devin": credentials["devin"],
        "openclaw": bool(os.environ.get("OPENCLAW_GATEWAY_URL") and
                         os.environ.get("OPENCLAW_GATEWAY_TOKEN")),
    }
    return [{**provider, "configured": configured[provider["id"]]} for provider in PROVIDERS]
