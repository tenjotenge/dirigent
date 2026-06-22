"""
Execution engine for Dirigent.

Central orchestrator that coordinates providers and tools.
"""
from typing import Dict, Any, List, Optional
from backend.core.interfaces import BaseProvider, BaseTool, ProviderResponse, ToolResult
from backend.core.tool_protocol import ToolCallBatch, ToolCallResult, PolicyDecision
from backend.tools.registry import ToolRegistry
from backend.executor.policy import PolicyEngine


class ExecutionEngine:
    """
    Central execution engine that orchestrates provider calls and tool execution.
    
    This is the only component that should directly call providers and tools.
    API endpoints should only interact with this engine.
    
    The engine now includes policy evaluation to ensure safe tool execution.
    """
    
    def __init__(self, provider: BaseProvider, tool_registry: ToolRegistry):
        """
        Initialize the execution engine.
        
        Args:
            provider: The provider instance to use for generation
            tool_registry: The tool registry for tool lookup
        """
        self.provider = provider
        self.tool_registry = tool_registry
        self.policy_engine = PolicyEngine(tool_registry.list_names())
    
    def execute(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a user request through the provider and handle any tool calls.
        
        Args:
            prompt: The user's input prompt
            model: The model to use
            **kwargs: Additional parameters for the provider
            
        Returns:
            Unified response dictionary containing:
            - content: The main response content
            - tool_results: List of tool execution results (if any)
            - policy_decision: Policy evaluation results
            - metadata: Provider metadata
        """
        # Step 1: Call provider
        provider_response = self.provider.send(prompt, model, **kwargs)
        
        # Step 2: Normalize tool calls
        tool_call_batch = provider_response.tool_calls
        
        # Step 3: Policy evaluation
        policy_decision = None
        tool_call_results = []
        
        if tool_call_batch and tool_call_batch:
            policy_decision = self.policy_engine.evaluate(tool_call_batch)
            
            # Step 4: Execute auto-approved calls; defer confirmation-required calls
            auto_calls = [
                call for call in policy_decision.allowed_calls
                if not call.requires_confirmation
            ]
            if auto_calls:
                tool_call_results = self._execute_tool_calls(auto_calls)
        
        # Step 5: Return unified response with policy decisions
        return {
            "content": provider_response.content,
            "tool_results": self._serialize_tool_results(tool_call_results),
            "policy_decision": self._serialize_policy_decision(policy_decision) if policy_decision else None,
            "metadata": provider_response.metadata,
        }
    
    def execute_tool_direct(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        """
        Execute a tool directly without going through a provider.
        
        This is used for explicit tool invocations from the UI.
        These bypass policy evaluation as they are user-initiated.
        
        Args:
            tool_name: The name of the tool to execute
            args: Arguments for the tool
            
        Returns:
            ToolResult from the tool execution
        """
        if not self.tool_registry.has(tool_name):
            return ToolResult(
                success=False,
                stderr=f"Tool not found: {tool_name}",
            )
        
        tool = self.tool_registry.get(tool_name)
        return tool.run(args)
    
    def _execute_tool_calls(self, tool_calls: List) -> List[ToolCallResult]:
        """
        Execute a list of tool calls.
        
        Args:
            tool_calls: List of ToolCall objects to execute
            
        Returns:
            List of ToolCallResult objects
        """
        results = []
        
        for tool_call in tool_calls:
            tool_result = self._execute_single_tool(tool_call)
            
            results.append(ToolCallResult(
                call_id=tool_call.call_id,
                success=tool_result.success,
                result=tool_result,
                error=tool_result.stderr,
                tool_name=tool_call.tool_name,
                args=tool_call.args,
            ))
        
        return results
    
    def _execute_single_tool(self, tool_call) -> ToolResult:
        """
        Execute a single tool call.
        
        Args:
            tool_call: The ToolCall object to execute
            
        Returns:
            ToolResult from the tool execution
        """
        tool_name = tool_call.tool_name
        
        if not self.tool_registry.has(tool_name):
            return ToolResult(
                success=False,
                stderr=f"Tool not found: {tool_name}",
            )
        
        tool = self.tool_registry.get(tool_name)
        return tool.run(tool_call.args)
    
    def _serialize_tool_result(self, tool_result: ToolResult) -> Dict[str, Any]:
        """Serialize a ToolResult for JSON response."""
        return {
            "success": tool_result.success,
            "stdout": tool_result.stdout,
            "stderr": tool_result.stderr,
            "data": tool_result.data,
        }

    def _serialize_tool_results(self, tool_call_results: List[ToolCallResult]) -> List[Dict[str, Any]]:
        """Serialize tool call results for JSON response."""
        return [
            {
                "call_id": result.call_id,
                "success": result.success,
                "tool_name": result.tool_name,
                "args": result.args,
                "error": result.error,
                "result": self._serialize_tool_result(result.result) if result.result else None,
            }
            for result in tool_call_results
        ]

    def _serialize_policy_decision(self, policy_decision: PolicyDecision) -> Dict[str, Any]:
        """
        Serialize a PolicyDecision for JSON response.
        
        Args:
            policy_decision: The PolicyDecision to serialize
            
        Returns:
            Dictionary representation of the policy decision
        """
        auto_allowed = [
            call for call in policy_decision.allowed_calls
            if not call.requires_confirmation
        ]
        pending_confirmation = [
            call for call in policy_decision.allowed_calls
            if call.requires_confirmation
        ]

        return {
            "allowed_calls": [
                {
                    "tool_name": call.tool_name,
                    "call_id": call.call_id,
                    "args": call.args,
                    "requires_confirmation": False,
                    "reason": policy_decision.reasons.get(call.call_id),
                }
                for call in auto_allowed
            ],
            "pending_confirmation_calls": [
                {
                    "tool_name": call.tool_name,
                    "call_id": call.call_id,
                    "args": call.args,
                    "requires_confirmation": True,
                    "reason": policy_decision.reasons.get(call.call_id),
                }
                for call in pending_confirmation
            ],
            "blocked_calls": [
                {
                    "tool_name": call.tool_name,
                    "call_id": call.call_id,
                    "args": call.args,
                    "reason": policy_decision.reasons.get(call.call_id),
                }
                for call in policy_decision.blocked_calls
            ],
            "requires_user_confirmation": policy_decision.requires_user_confirmation,
            "reasons": policy_decision.reasons,
        }
    
    def list_models(self) -> List[str]:
        """List available models from the provider."""
        return self.provider.list_models()
    
    def health_check(self) -> bool:
        """Check if the provider is available."""
        return self.provider.health_check()

    def refresh_provider(self) -> None:
        """Reload provider configuration from current settings."""
        self.provider.refresh_config()
    
    def list_tools(self) -> List[str]:
        """List available tools."""
        return list(self.tool_registry.list_names())
