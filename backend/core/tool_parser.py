"""
Robust tool call parser for Dirigent.

Handles ALL input types from LM Studio and normalizes them into ToolCallBatch or None.
Never guesses or hallucinates tools - only parses what is explicitly present.
"""
import json
import re
import uuid
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from backend.core.tool_protocol import ToolCall, ToolCallBatch, ExecutionMode


@dataclass
class ParseResult:
    """Result of parsing LLM output for tool calls."""
    tool_calls: Optional[ToolCallBatch]
    raw_output: str
    parse_success: bool
    parse_method: str
    error: Optional[str] = None
    confidence: float = 1.0


class ToolCallParser:
    """
    Parser layer that handles all LLM output formats and normalizes to ToolCallBatch.
    
    Input types handled:
    - Pure JSON tool calls
    - Embedded JSON in text
    - Malformed JSON
    - Partial tool calls
    - Natural language instructions
    
    Output is ALWAYS:
    - ToolCallBatch (possibly empty) OR null
    - Never guesses or hallucinates tools
    """
    
    # Regex patterns for extracting tool calls from text
    PATTERNS = [
        # JSON code blocks
        r'```(?:json)?\s*(\{.*?\})\s*```',
        # Inline JSON objects with tool-like structure
        r'\{(?:\s*"tool_name"\s*:\s*"[^"]+"\s*,\s*"args"\s*:\s*\{.*?\}\s*)\}',
        # Tool call blocks (custom format)
        r'\[TOOL_CALL\](.*?)\[/TOOL_CALL\]',
        # Function call format
        r'function_call\s*:\s*(\{.*?\})',
    ]
    
    def __init__(self, registered_tools: Optional[List[str]] = None):
        """
        Initialize the parser.
        
        Args:
            registered_tools: List of valid tool names for validation
        """
        self.registered_tools = set(registered_tools or [])
    
    def parse(self, raw_output: str) -> ParseResult:
        """
        Parse LLM output and extract tool calls.
        
        Args:
            raw_output: Raw text output from LLM
            
        Returns:
            ParseResult with tool_calls (ToolCallBatch or None) and metadata
        """
        if not raw_output or not raw_output.strip():
            return ParseResult(
                tool_calls=None,
                raw_output=raw_output,
                parse_success=True,
                parse_method="empty_input",
                confidence=1.0,
            )
        
        # Strategy 1: Try strict JSON parse of entire output
        result = self._try_strict_json_parse(raw_output)
        if result:
            return result
        
        # Strategy 2: Try regex extraction of tool blocks
        result = self._try_regex_extraction(raw_output)
        if result:
            return result
        
        # Strategy 3: No tool calls found - return plain text
        return ParseResult(
            tool_calls=None,
            raw_output=raw_output,
            parse_success=True,
            parse_method="no_tool_calls",
            confidence=1.0,
        )
    
    def _try_strict_json_parse(self, raw_output: str) -> Optional[ParseResult]:
        """
        Attempt to parse the entire output as JSON.
        
        Returns:
            ParseResult if successful, None otherwise
        """
        try:
            data = json.loads(raw_output.strip())
            
            # Check if it's a single tool call
            if isinstance(data, dict) and "tool_name" in data:
                tool_call = self._dict_to_tool_call(data, confidence=1.0)
                if tool_call:
                    return ParseResult(
                        tool_calls=ToolCallBatch(
                            calls=[tool_call],
                            source_provider="lmstudio",
                            metadata={"parse_method": "strict_json_single"},
                        ),
                        raw_output=raw_output,
                        parse_success=True,
                        parse_method="strict_json_single",
                        confidence=1.0,
                    )
            
            # Check if it's a batch of tool calls
            if isinstance(data, dict) and "calls" in data:
                calls = []
                for call_data in data.get("calls", []):
                    tool_call = self._dict_to_tool_call(call_data, confidence=1.0)
                    if tool_call:
                        calls.append(tool_call)
                
                if calls:
                    return ParseResult(
                        tool_calls=ToolCallBatch(
                            calls=calls,
                            execution_mode=ExecutionMode(data.get("execution_mode", "sequential")),
                            source_provider="lmstudio",
                            metadata={"parse_method": "strict_json_batch"},
                        ),
                        raw_output=raw_output,
                        parse_success=True,
                        parse_method="strict_json_batch",
                        confidence=1.0,
                    )
            
            # Check if it's a list of tool calls
            if isinstance(data, list):
                calls = []
                for call_data in data:
                    if isinstance(call_data, dict) and "tool_name" in call_data:
                        tool_call = self._dict_to_tool_call(call_data, confidence=1.0)
                        if tool_call:
                            calls.append(tool_call)
                
                if calls:
                    return ParseResult(
                        tool_calls=ToolCallBatch(
                            calls=calls,
                            source_provider="lmstudio",
                            metadata={"parse_method": "strict_json_list"},
                        ),
                        raw_output=raw_output,
                        parse_success=True,
                        parse_method="strict_json_list",
                        confidence=1.0,
                    )
            
            return None
            
        except (json.JSONDecodeError, ValueError, KeyError):
            return None
    
    def _try_regex_extraction(self, raw_output: str) -> Optional[ParseResult]:
        """
        Attempt to extract tool calls using regex patterns.
        
        Returns:
            ParseResult if successful, None otherwise
        """
        calls = []
        
        for pattern in self.PATTERNS:
            matches = re.findall(pattern, raw_output, re.DOTALL | re.IGNORECASE)
            
            for match in matches:
                try:
                    # Try to parse the matched content as JSON
                    if isinstance(match, str):
                        data = json.loads(match)
                    else:
                        data = match
                    
                    if isinstance(data, dict) and "tool_name" in data:
                        tool_call = self._dict_to_tool_call(data, confidence=0.7)
                        if tool_call:
                            calls.append(tool_call)
                    
                except (json.JSONDecodeError, ValueError, KeyError):
                    continue
        
        if calls:
            return ParseResult(
                tool_calls=ToolCallBatch(
                    calls=calls,
                    source_provider="lmstudio",
                    metadata={"parse_method": "regex_extraction"},
                ),
                raw_output=raw_output,
                parse_success=True,
                parse_method="regex_extraction",
                confidence=0.7,
            )
        
        return None
    
    def _dict_to_tool_call(self, data: Dict[str, Any], confidence: float = 1.0) -> Optional[ToolCall]:
        """
        Convert a dictionary to a ToolCall object.
        
        Validates that the tool is registered and arguments are valid.
        
        Args:
            data: Dictionary with tool call data
            confidence: Confidence score for this parse
            
        Returns:
            ToolCall if valid, None otherwise
        """
        tool_name = data.get("tool_name")
        
        if not tool_name:
            return None
        
        # Validate tool is registered
        if self.registered_tools and tool_name not in self.registered_tools:
            # Unknown tool - reject it
            return None
        
        # Extract arguments
        args = data.get("args", {})
        if not isinstance(args, dict):
            args = {}
        
        # Create tool call
        return ToolCall(
            tool_name=tool_name,
            args=args,
            call_id=data.get("call_id", str(uuid.uuid4())),
            requires_confirmation=data.get("requires_confirmation", False),
            confidence=confidence,
            metadata=data.get("metadata", {}),
        )
    
    def update_registered_tools(self, registered_tools: List[str]) -> None:
        """
        Update the list of registered tools for validation.
        
        Args:
            registered_tools: List of valid tool names
        """
        self.registered_tools = set(registered_tools)


def parse_tool_calls(raw_output: str, registered_tools: Optional[List[str]] = None) -> ParseResult:
    """
    Convenience function to parse tool calls from LLM output.
    
    Args:
        raw_output: Raw text output from LLM
        registered_tools: Optional list of valid tool names
        
    Returns:
        ParseResult with tool_calls (ToolCallBatch or None) and metadata
    """
    parser = ToolCallParser(registered_tools)
    return parser.parse(raw_output)