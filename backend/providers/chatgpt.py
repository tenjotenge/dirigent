"""ChatGPT plan provider using a locally authorized OAuth access token."""
import json
import time
from typing import Any, List, Optional

import requests

from backend.core.interfaces import BaseProvider, ProviderResponse
from backend.core.tool_parser import parse_tool_calls
from backend.openai_auth import OpenAIAuthError, chatgpt_auth


class ChatGPTProvider(BaseProvider):
    """Responses API adapter for a user's Sign in with ChatGPT connection."""

    def __init__(self, registered_tools: Optional[List[str]] = None):
        self.registered_tools = registered_tools or []

    def refresh_config(self) -> None:
        return

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {chatgpt_auth.active_access_token()}", "Content-Type": "application/json"}

    def list_models(self) -> List[str]:
        try:
            response = requests.get("https://api.openai.com/v1/models", headers=self._headers(), timeout=15)
            response.raise_for_status()
            return [item["slug"] for item in response.json().get("models", []) if item.get("visibility") == "list"]
        except (requests.RequestException, OpenAIAuthError):
            return []

    def health_check(self) -> bool:
        return bool(self.list_models())

    def send(self, prompt: str, model: str, **kwargs: Any) -> ProviderResponse:
        started = time.monotonic()
        payload = {"model": model, "input": [{"role": "user", "content": prompt}], "store": False, "stream": True}
        try:
            response = requests.post("https://api.openai.com/v1/responses", headers=self._headers(), json=payload, stream=True, timeout=None)
            response.raise_for_status()
            text_parts: list[str] = []
            completed = False
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line or not raw_line.startswith("data: "):
                    continue
                event = json.loads(raw_line[6:])
                if event.get("type") == "response.output_text.delta":
                    text_parts.append(event.get("delta", ""))
                elif event.get("type") == "response.failed":
                    raise RuntimeError(event.get("response", {}).get("error", {}).get("message", "ChatGPT request failed"))
                elif event.get("type") == "response.completed":
                    completed = True
            if not completed:
                raise RuntimeError("ChatGPT response ended before response.completed.")
            content = "".join(text_parts)
            parsed = parse_tool_calls(content, self.registered_tools)
            return ProviderResponse(content=content, tool_calls=parsed.tool_calls, metadata={"model": model, "provider": "chatgpt", "generation_time_seconds": round(time.monotonic() - started, 2), "parse_method": parsed.parse_method})
        except (requests.RequestException, OpenAIAuthError, ValueError) as exc:
            raise RuntimeError(f"ChatGPT generation failed: {exc}") from exc
