"""Perplexity Agent API adapter for direct, tool-free model generation."""
from __future__ import annotations

import time
from typing import Any, Optional

import requests

from backend.core.interfaces import BaseProvider, ProviderResponse
from backend.core.tool_parser import parse_tool_calls
from backend.provider_credentials import ProviderCredentialError, provider_credentials

API_ROOT = "https://api.perplexity.ai/v1"


class PerplexityProvider(BaseProvider):
    def __init__(self, registered_tools: Optional[list[str]] = None):
        self.registered_tools = registered_tools or []

    @staticmethod
    def _headers() -> dict[str, str]:
        secret = provider_credentials.get_secret("perplexity")
        if not secret:
            raise ProviderCredentialError("Perplexity API key is not configured")
        return {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}

    def list_models(self) -> list[str]:
        try:
            response = requests.get(f"{API_ROOT}/models", headers=self._headers(), timeout=10)
            response.raise_for_status()
            data = response.json()
            return [item["id"] for item in data.get("data", [])
                    if isinstance(item, dict) and isinstance(item.get("id"), str)]
        except (requests.RequestException, ProviderCredentialError, ValueError, KeyError, AttributeError, TypeError):
            return []

    def health_check(self) -> bool:
        return bool(self.list_models())

    def send(self, prompt: str, model: str, **kwargs: Any) -> ProviderResponse:
        payload: dict[str, Any] = {
            "model": model,
            "input": prompt,
            "tools": [],
            "store": False,
        }
        if kwargs.get("max_tokens") is not None:
            payload["max_output_tokens"] = kwargs["max_tokens"]
        if kwargs.get("effort"):
            payload["reasoning"] = {"effort": kwargs["effort"]}

        started = time.monotonic()
        try:
            response = requests.post(f"{API_ROOT}/agent", headers=self._headers(),
                                     json=payload, timeout=(10, None))
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ProviderCredentialError, ValueError) as exc:
            raise RuntimeError(f"Perplexity API request failed: {exc}") from exc

        if not isinstance(data, dict) or data.get("status") != "completed" or not isinstance(data.get("output"), list):
            raise RuntimeError("Perplexity API returned an incomplete or invalid response")
        parts: list[str] = []
        for item in data["output"]:
            if not isinstance(item, dict) or item.get("type") != "message" or item.get("role") != "assistant":
                continue
            for block in item.get("content", []):
                if isinstance(block, dict) and block.get("type") == "output_text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
        content = "".join(parts)
        parsed = parse_tool_calls(content, self.registered_tools)
        metadata: dict[str, Any] = {
            "provider": "perplexity",
            "model": data.get("model") or model,
            "generation_time_seconds": round(time.monotonic() - started, 2),
            "parse_method": parsed.parse_method,
        }
        if data.get("id"):
            metadata["response_id"] = data["id"]
        if isinstance(data.get("usage"), dict):
            metadata["usage"] = data["usage"]
        reasoning = data.get("reasoning")
        if isinstance(reasoning, dict) and isinstance(reasoning.get("effort"), str):
            metadata["reasoning_effort"] = reasoning["effort"]
        return ProviderResponse(content=content, tool_calls=parsed.tool_calls, metadata=metadata)
