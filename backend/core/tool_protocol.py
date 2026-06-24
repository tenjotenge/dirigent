"""
Unified tool calling protocol for Dirigent.

Defines provider-agnostic schemas for tool execution across all AI providers.
This ensures Claude, ChatGPT, Codex, and Devin can all express actions uniformly.
"""
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class ExecutionMode(str, Enum):
    """Execution mode for tool call batches."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


@dataclass
class ToolCall:
    """
    Represents a single tool call request from a provider.
    
    This is the universal schema that all providers must conform to,
    regardless of their native tool calling format.
    """
    tool_name: str
    args: Dict[str, Any]
    call_id: Optional[str] = None
    requires_confirmation: bool = False
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.call_id is None:
            self.call_id = str(uuid.uuid4())


@dataclass
class ToolCallBatch:
    """
    Represents a batch of tool calls from a provider.
    
    Allows providers to request multiple tool executions in a single response.
    """
    calls: List[ToolCall]
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    source_provider: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __len__(self) -> int:
        return len(self.calls)
    
    def __bool__(self) -> bool:
        return len(self.calls) > 0


@dataclass
class ToolCallResult:
    """
    Represents the result of executing a single tool call.
    """
    call_id: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    
    # Include the original tool call for reference
    tool_name: Optional[str] = None
    args: Optional[Dict[str, Any]] = None


@dataclass
class PolicyDecision:
    """
    Represents a policy engine decision on a tool call batch.
    
    The policy engine evaluates tool calls and determines:
    - which calls are allowed to execute
    - which calls are blocked
    - whether user confirmation is required
    - reasons for decisions
    """
    allowed_calls: List[ToolCall]
    blocked_calls: List[ToolCall]
    requires_user_confirmation: bool
    reasons: Dict[str, str] = field(default_factory=dict)
    
    @property
    def has_allowed_calls(self) -> bool:
        return len(self.allowed_calls) > 0
    
    @property
    def has_blocked_calls(self) -> bool:
        return len(self.blocked_calls) > 0
