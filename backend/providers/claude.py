"""Direct Claude Messages API adapter (separate from Claude subscription login)."""
from __future__ import annotations

import os
import time
from typing import Any, Optional

import requests

from backend.core.interfaces import BaseProvider, ProviderResponse
from backend.core.tool_parser import parse_tool_calls
from backend.provider_credentials import ProviderCredentialError, provider_credentials

API_ROOT = "https://api.anthropic.com/v1"
API_VERSION = "2023-06-01"
SUPPORTED_EFFORT = {"low", "medium", "high", "xhigh", "max"}


class ClaudeProvider(BaseProvider):
    def __init__(self, registered_tools: Optional[list[str]] = None):
        self.registered_tools = registered_tools or []

    @staticmethod
    def _headers() -> dict[str, str]:
        secret = provider_credentials.get_secret("claude")
        if not secret:
            raise ProviderCredentialError("Claude API key is not configured")
        headers = {"x-api-key": secret, "anthropic-version": API_VERSION,
                   "Content-Type": "application/json"}
        workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID", "").strip()
        if workspace_id:
            headers["anthropic-workspace-id"] = workspace_id
        return headers

    def list_models(self) -> list[str]:
        try:
            response = requests.get(f"{API_ROOT}/models", headers=self._headers(),
                                    params={"limit": 100}, timeout=10)
            response.raise_for_status()
            data = response.json()
            return [item["id"] for item in data.get("data", [])
                    if isinstance(item, dict) and isinstance(item.get("id"), str)]
        except (requests.RequestException, ProviderCredentialError, ValueError, KeyError, AttributeError, TypeError):
            return []

    def health_check(self) -> bool:
        return bool(self.list_models())

    def send(self, prompt: str, model: str, **kwargs: Any) -> ProviderResponse:
        effort = kwargs.get("effort")
        if effort is not None and effort not in SUPPORTED_EFFORT:
            raise ValueError(f"Unsupported Claude effort: {effort}")
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": kwargs.get("max_tokens") or 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
        if effort:
            payload["output_config"] = {"effort": effort}
        started = time.monotonic()
        try:
            response = requests.post(f"{API_ROOT}/messages", headers=self._headers(),
                                     json=payload, timeout=(10, None))
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ProviderCredentialError, ValueError) as exc:
            raise RuntimeError(f"Claude API request failed: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("content"), list):
            raise RuntimeError("Claude API returned an invalid message")
        content = "".join(block["text"] for block in data["content"]
                          if isinstance(block, dict) and block.get("type") == "text"
                          and isinstance(block.get("text"), str))
        parsed = parse_tool_calls(content, self.registered_tools)
        metadata: dict[str, Any] = {
            "provider": "claude", "model": data.get("model") or model,
            "generation_time_seconds": round(time.monotonic() - started, 2),
            "parse_method": parsed.parse_method,
        }
        if effort:
            metadata["reasoning_effort"] = effort
        if isinstance(data.get("usage"), dict):
            metadata["usage"] = data["usage"]
        if data.get("stop_reason"):
            metadata["stop_reason"] = data["stop_reason"]
        return ProviderResponse(content=content, tool_calls=parsed.tool_calls, metadata=metadata)
