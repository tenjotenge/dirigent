"""
LM Studio provider implementation.
"""
import logging
import time
import requests
from typing import List, Dict, Any, Optional
from enum import Enum
from backend.core.interfaces import BaseProvider, ProviderResponse
from backend.core.tool_protocol import ToolCallBatch
from backend.core.tool_parser import parse_tool_calls
from backend.config import settings

logger = logging.getLogger(__name__)


class GenerationState(Enum):
    """Generation lifecycle states."""
    IDLE = "idle"
    REQUEST_SENT = "request_sent"
    WAITING_FOR_FIRST_TOKEN = "waiting_for_first_token"
    STREAMING = "streaming"
    COMPLETING = "completing"
    COMPLETE = "complete"


class LMStudioProvider(BaseProvider):
    """Provider for LM Studio local API."""

    # Adaptive latency profiles per model type (in seconds)
    LATENCY_PROFILES = {
        "fast": {"expected_min": 5, "expected_max": 20, "watchdog_interval": 10},
        "medium": {"expected_min": 20, "expected_max": 120, "watchdog_interval": 30},
        "large": {"expected_min": 120, "expected_max": 600, "watchdog_interval": 60},
        "xlarge": {"expected_min": 600, "expected_max": 3600, "watchdog_interval": 120},
    }

    def __init__(self, registered_tools: Optional[List[str]] = None):
        self.refresh_config()
        self.registered_tools = registered_tools or []
        self.current_state = GenerationState.IDLE
        self.request_start_time = None
        self.last_watchdog_log = None

    def refresh_config(self) -> None:
        """Reload endpoint from current settings."""
        self.base_url = f"http://{settings.lmstudio_host}:{settings.lmstudio_port}/v1"
    
    def update_registered_tools(self, registered_tools: List[str]) -> None:
        """Update the list of registered tools for parsing."""
        self.registered_tools = registered_tools
    
    def _get_latency_profile(self, model: str) -> Dict[str, int]:
        """
        Get latency profile for a model.
        
        Uses model name heuristics to determine expected latency.
        """
        model_lower = model.lower()
        
        # Heuristic matching for model size
        if any(x in model_lower for x in ["tiny", "small", "mini", "fast"]):
            return self.LATENCY_PROFILES["fast"]
        elif any(x in model_lower for x in ["medium", "base", "7b", "8b"]):
            return self.LATENCY_PROFILES["medium"]
        elif any(x in model_lower for x in ["large", "13b", "14b", "20b", "34b"]):
            return self.LATENCY_PROFILES["large"]
        else:
            # Default to large profile for unknown models
            return self.LATENCY_PROFILES["large"]
    
    def _watchdog_log(self, model: str, elapsed: float) -> None:
        """
        Log generation progress without treating slowness as failure.
        
        Args:
            model: Model name
            elapsed: Elapsed time in seconds
        """
        profile = self._get_latency_profile(model)
        expected_max = profile["expected_max"]
        watchdog_interval = profile["watchdog_interval"]
        
        # Only log at watchdog intervals
        if self.last_watchdog_log is None or (elapsed - self.last_watchdog_log) >= watchdog_interval:
            if elapsed < expected_max:
                logger.info(f"Generation in progress: model={model}, elapsed={elapsed:.1f}s (expected max: {expected_max}s)")
            else:
                logger.warning(
                    f"Generation taking longer than expected: model={model}, "
                    f"elapsed={elapsed:.1f}s (expected max: {expected_max}s) - still waiting..."
                )
            self.last_watchdog_log = elapsed
    
    def send(self, prompt: str, model: str, **kwargs) -> ProviderResponse:
        """
        Send a prompt to LM Studio and return a structured response.
        
        Always normalizes output through the tool parser to ensure
        deterministic tool call extraction. Supports long-running
        generations without timeout.
        """
        self.current_state = GenerationState.REQUEST_SENT
        self.request_start_time = time.time()
        self.last_watchdog_log = None
        
        try:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2048),
            }
            
            # NO TIMEOUT - allow generation to run as long as needed
            # Only user cancellation should stop generation
            logger.info(f"Sending request to LM Studio: model={model}, state={self.current_state.value}")
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=None  # No timeout - wait indefinitely for completion
            )
            
            elapsed = time.time() - self.request_start_time
            self._watchdog_log(model, elapsed)
            
            self.current_state = GenerationState.COMPLETING
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            self.current_state = GenerationState.COMPLETE
            total_elapsed = time.time() - self.request_start_time
            
            logger.info(
                f"LM Studio response received: model={model}, "
                f"elapsed={total_elapsed:.1f}s, "
                f"content_length={len(content)}"
            )
            
            # Log raw output for debugging (truncated for readability)
            logger.debug(f"LM Studio raw output for model {model}: {content[:500]}...")
            
            # Parse tool calls from the COMPLETE output only
            parse_result = parse_tool_calls(content, self.registered_tools)
            
            # Log parsing results
            if parse_result.parse_method != "no_tool_calls" and parse_result.parse_method != "empty_input":
                logger.info(
                    f"Tool parsing: method={parse_result.parse_method}, "
                    f"success={parse_result.parse_success}, "
                    f"calls_found={len(parse_result.tool_calls.calls) if parse_result.tool_calls else 0}, "
                    f"confidence={parse_result.confidence}"
                )
            elif not parse_result.parse_success:
                logger.warning(
                    f"Tool parsing failed: method={parse_result.parse_method}, "
                    f"error={parse_result.error}"
                )
            
            # Build metadata
            metadata = {
                "model": model,
                "provider": "lmstudio",
                "parse_method": parse_result.parse_method,
                "parse_success": parse_result.parse_success,
                "raw_output_length": len(content),
                "generation_time_seconds": round(total_elapsed, 2),
                "generation_state": self.current_state.value,
            }
            
            if parse_result.error:
                metadata["parse_error"] = parse_result.error
            
            # Return normalized response
            return ProviderResponse(
                content=content,
                tool_calls=parse_result.tool_calls,
                metadata=metadata,
            )
        except requests.exceptions.Timeout:
            elapsed = time.time() - self.request_start_time
            logger.error(f"LM Studio request timeout after {elapsed:.1f}s: model={model}")
            self.current_state = GenerationState.IDLE
            raise Exception(f"LM Studio request timeout after {elapsed:.1f}s")
        except Exception as e:
            elapsed = time.time() - self.request_start_time if self.request_start_time else 0
            logger.error(f"LM Studio generation failed after {elapsed:.1f}s: model={model}, error={str(e)}")
            self.current_state = GenerationState.IDLE
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
