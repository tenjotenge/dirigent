"""
Core interfaces for Dirigent architecture.

Defines the contracts between Provider Layer, Execution Layer, and Tool Layer.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from backend.core.tool_protocol import ToolCallBatch


@dataclass
class ProviderResponse:
    """Structured response from a provider."""
    content: str
    tool_calls: Optional[ToolCallBatch] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Structured result from a tool execution."""
    success: bool
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class BaseProvider(ABC):
    """Abstract base class for all providers."""
    
    @abstractmethod
    def send(self, prompt: str, model: str, **kwargs) -> ProviderResponse:
        """
        Send a prompt to the provider and get a structured response.
        
        Args:
            prompt: The input prompt to send
            model: The model identifier to use
            **kwargs: Additional provider-specific parameters
            
        Returns:
            ProviderResponse with content, optional tool_calls, and metadata
        """
        pass
    
    @abstractmethod
    def list_models(self) -> List[str]:
        """List available models from this provider."""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check if the provider is available."""
        pass


class BaseTool(ABC):
    """Abstract base class for all tools."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The unique name of this tool."""
        pass
    
    @abstractmethod
    def run(self, args: Dict[str, Any]) -> ToolResult:
        """
        Execute the tool with given arguments.
        
        Args:
            args: Dictionary of arguments for the tool
            
        Returns:
            ToolResult with execution status and outputs
        """
        pass
