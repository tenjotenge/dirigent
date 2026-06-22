"""
Tool registry for Dirigent.

Central registry for all available tools.
No tool should ever be imported directly in ExecutionEngine.
"""
from typing import Dict, Set
from backend.core.interfaces import BaseTool


class ToolRegistry:
    """
    Central registry for tool instances.
    
    Provides lookup and management of all available tools.
    """
    
    def __init__(self):
        """Initialize an empty tool registry."""
        self._tools: Dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool) -> None:
        """
        Register a tool in the registry.
        
        Args:
            tool: The tool instance to register
            
        Raises:
            ValueError: If a tool with the same name is already registered
        """
        tool_name = tool.name
        if tool_name in self._tools:
            raise ValueError(f"Tool '{tool_name}' is already registered")
        
        self._tools[tool_name] = tool
    
    def get(self, tool_name: str) -> BaseTool:
        """
        Get a tool by name.
        
        Args:
            tool_name: The name of the tool to retrieve
            
        Returns:
            The tool instance
            
        Raises:
            KeyError: If the tool is not registered
        """
        if tool_name not in self._tools:
            raise KeyError(f"Tool '{tool_name}' is not registered")
        
        return self._tools[tool_name]
    
    def has(self, tool_name: str) -> bool:
        """
        Check if a tool is registered.
        
        Args:
            tool_name: The name of the tool to check
            
        Returns:
            True if the tool is registered, False otherwise
        """
        return tool_name in self._tools
    
    def list_names(self) -> Set[str]:
        """
        Get all registered tool names.
        
        Returns:
            Set of registered tool names
        """
        return set(self._tools.keys())
    
    def list_all(self) -> Dict[str, BaseTool]:
        """
        Get all registered tools.
        
        Returns:
            Dictionary mapping tool names to tool instances
        """
        return self._tools.copy()
    
    def unregister(self, tool_name: str) -> None:
        """
        Unregister a tool.
        
        Args:
            tool_name: The name of the tool to unregister
            
        Raises:
            KeyError: If the tool is not registered
        """
        if tool_name not in self._tools:
            raise KeyError(f"Tool '{tool_name}' is not registered")
        
        del self._tools[tool_name]


# Global registry instance
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """
    Get the global tool registry instance.
    
    Returns:
        The global ToolRegistry instance
    """
    return _registry


def register_tool(tool: BaseTool) -> None:
    """
    Register a tool in the global registry.
    
    Args:
        tool: The tool instance to register
    """
    _registry.register(tool)


def get_tool(tool_name: str) -> BaseTool:
    """
    Get a tool by name from the global registry.
    
    Args:
        tool_name: The name of the tool to retrieve
        
    Returns:
        The tool instance
    """
    return _registry.get(tool_name)
