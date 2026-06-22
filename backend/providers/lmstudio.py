"""
LM Studio provider implementation.
"""
import requests
from typing import List, Dict, Any
from backend.core.interfaces import BaseProvider, ProviderResponse
from backend.config import settings


class LMStudioProvider(BaseProvider):
    """Provider for LM Studio local API."""

    def __init__(self):
        self.refresh_config()

    def refresh_config(self) -> None:
        """Reload endpoint from current settings."""
        self.base_url = f"http://{settings.lmstudio_host}:{settings.lmstudio_port}/v1"
    
    def send(self, prompt: str, model: str, **kwargs) -> ProviderResponse:
        """Send a prompt to LM Studio and return a structured response."""
        try:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2048),
            }
            response = requests.post(f"{self.base_url}/chat/completions", json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            # Return structured response with None for tool_calls
            # LM Studio doesn't currently support structured tool calling,
            # but the interface is ready for future adapter implementation
            return ProviderResponse(
                content=content,
                tool_calls=None,
                metadata={
                    "model": model,
                    "provider": "lmstudio",
                },
            )
        except Exception as e:
            raise Exception(f"LM Studio generation failed: {str(e)}")
    
    def list_models(self) -> List[str]:
        """List available models from LM Studio."""
        try:
            response = requests.get(f"{self.base_url}/models", timeout=5)
            response.raise_for_status()
            data = response.json()
            return [model["id"] for model in data.get("data", [])]
        except Exception as e:
            return []
    
    def health_check(self) -> bool:
        """Check if LM Studio is available."""
        try:
            response = requests.get(f"{self.base_url}/models", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
