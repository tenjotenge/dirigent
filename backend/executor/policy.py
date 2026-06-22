"""
Execution policy layer for Dirigent.

The policy engine evaluates tool calls and determines:
- which calls are allowed to execute
- which calls are blocked
- whether user confirmation is required
- reasons for decisions

This ensures safe and controlled tool execution across all providers.
"""
from typing import List, Dict, Set
from backend.core.tool_protocol import ToolCall, ToolCallBatch, PolicyDecision


class PolicyEngine:
    """
    Policy engine for evaluating tool call permissions.
    
    Implements deterministic rules for tool execution safety.
    """
    
    # Policy rules
    ALLOWED_TOOLS: Set[str] = {
        "read_file",
        "git_status",
    }
    
    CONFIRMATION_REQUIRED_TOOLS: Set[str] = {
        "write_file",
        "git_add",
        "git_commit",
        "git_push",
    }
    
    def __init__(self, registered_tools: Set[str]):
        """
        Initialize the policy engine.
        
        Args:
            registered_tools: Set of tool names that are actually registered
        """
        self.registered_tools = registered_tools
    
    def evaluate(self, tool_call_batch: ToolCallBatch) -> PolicyDecision:
        """
        Evaluate a tool call batch against policy rules.
        
        Args:
            tool_call_batch: The batch of tool calls to evaluate
            
        Returns:
            PolicyDecision with allowed calls, blocked calls, and confirmation requirements
        """
        allowed_calls: List[ToolCall] = []
        blocked_calls: List[ToolCall] = []
        reasons: Dict[str, str] = {}
        requires_confirmation = False
        
        for call in tool_call_batch.calls:
            decision = self._evaluate_single_call(call)
            
            if decision["allowed"]:
                if decision["requires_confirmation"]:
                    call.requires_confirmation = True
                    requires_confirmation = True
                allowed_calls.append(call)
            else:
                blocked_calls.append(call)
            
            if decision["reason"]:
                reasons[call.call_id] = decision["reason"]
        
        return PolicyDecision(
            allowed_calls=allowed_calls,
            blocked_calls=blocked_calls,
            requires_user_confirmation=requires_confirmation,
            reasons=reasons,
        )
    
    def _evaluate_single_call(self, call: ToolCall) -> Dict[str, any]:
        """
        Evaluate a single tool call against policy rules.
        
        Args:
            call: The tool call to evaluate
            
        Returns:
            Dictionary with allowed, requires_confirmation, and reason keys
        """
        # Rule 1: Tool must be registered
        if call.tool_name not in self.registered_tools:
            return {
                "allowed": False,
                "requires_confirmation": False,
                "reason": f"Tool '{call.tool_name}' is not registered",
            }
        
        # Rule 2: Check if tool is explicitly allowed
        if call.tool_name in self.ALLOWED_TOOLS:
            return {
                "allowed": True,
                "requires_confirmation": False,
                "reason": None,
            }
        
        # Rule 3: Check if tool requires confirmation
        if call.tool_name in self.CONFIRMATION_REQUIRED_TOOLS:
            return {
                "allowed": True,
                "requires_confirmation": True,
                "reason": f"Tool '{call.tool_name}' requires user confirmation",
            }
        
        # Rule 4: Default deny for unknown tools
        return {
            "allowed": False,
            "requires_confirmation": False,
            "reason": f"Tool '{call.tool_name}' is not in allowed policy",
        }
    
    def update_registered_tools(self, registered_tools: Set[str]) -> None:
        """
        Update the set of registered tools.
        
        Args:
            registered_tools: New set of registered tool names
        """
        self.registered_tools = registered_tools
