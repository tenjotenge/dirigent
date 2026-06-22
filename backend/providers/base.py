"""
Base provider interface.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseProvider(ABC):
    """Abstract base class for all providers."""
    
    @abstractmethod
    def list_models(self) -> List[str]:
        """List available models from this provider."""
        pass
    
    @abstractmethod
    def generate(self, model: str, prompt: str, **kwargs) -> str:
        """Generate text using the specified model."""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check if the provider is available."""
        pass
