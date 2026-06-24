# Tool Execution Contract Stabilization (v0.4)

## Summary

This document describes the tool execution contract stabilization implemented for Dirigent to ensure deterministic, reliable tool calling from LM Studio models.

## Problem Solved

**Before:** LM Studio models (especially Mistral) produced inconsistent tool call formats:
- Ignored tool format entirely
- Output natural language instead of structured calls
- Partially formatted tool calls
- Failed to trigger ExecutionEngine

**After:** All LLM outputs are normalized through a strict pipeline that either:
- Extracts valid tool calls and executes them deterministically, OR
- Safely ignores the output as plain text

## Architecture

### Execution Flow (Deterministic)

```
LM Studio Response
    ↓
Tool Parser (normalize output)
    ↓
Execution Gate (validate tool calls)
    ↓
Policy Engine (allow/confirm/deny)
    ↓
Execution Engine (execute tools)
    ↓
Tool Result
    ↓
UI Update
```

**No shortcuts. No direct execution from raw LLM output.**

## Components

### 1. Strict Tool-Call Schema (`backend/core/tool_protocol.py`)

**ToolCall:**
- `tool_name`: string (required)
- `args`: dict (required)
- `call_id`: optional uuid (auto-generated if missing)
- `confidence`: optional float (0.0-1.0)
- `requires_confirmation`: bool
- `metadata`: dict

**ToolCallBatch:**
- `calls`: List[ToolCall]
- `execution_mode`: SEQUENTIAL | PARALLEL
- `source_provider`: string
- `metadata`: dict

**Rules:**
- Only tools in ToolRegistry are valid
- Unknown tools are rejected (not executed)
- Arguments must be JSON-parsable

### 2. Robust Tool Parser (`backend/core/tool_parser.py`)

**Handles ALL input types:**
- Pure JSON tool calls
- Embedded JSON in text
- Malformed JSON
- Partial tool calls
- Natural language instructions

**Parser Strategy:**
1. Attempt strict JSON parse of entire output
2. If fail, attempt regex extraction of tool blocks
3. If fail, return NONE (no execution)
4. **NEVER guesses or hallucinates tools**

**Output:** ToolCallBatch OR null

### 3. Provider Normalization (`backend/providers/lmstudio.py`)

**LMStudioProvider.send() now:**
- Always parses output through tool parser
- Returns normalized ProviderResponse with:
  - `content`: string (raw text)
  - `tool_calls`: ToolCallBatch | None
  - `metadata`: dict with parse info
- Logs raw output, parse method, and results

### 4. Execution Gate (`backend/executor/engine.py`)

**Validation before execution:**
- Tool exists in ToolRegistry
- Tool call is not malformed
- Arguments are JSON-serializable
- Confidence check (low confidence → confirmation required)

**If ANY validation fails:**
- Do NOT execute
- Log error in execution log
- Return validation_errors to UI

### 5. Policy Engine (`backend/executor/policy.py`)

**Enhanced with confidence handling:**
- Rule 0: Low confidence (< 0.5) → require confirmation
- Rule 1: Tool must be registered
- Rule 2: Explicitly allowed tools → auto-execute
- Rule 3: Confirmation-required tools → user approval
- Rule 4: Unknown tools → deny

### 6. Logging & Debugging

**Comprehensive logging at every stage:**
- Raw LM Studio output (debug level)
- Parsed tool calls (info level)
- Parsing failures and reasons (warning level)
- Validation failures and reasons (warning level)
- Policy decisions (info level)
- Execution results (info/error level)

**Makes tool failures diagnosable in seconds.**

## Key Features

### Confidence Handling

- **High confidence (≥ 0.5):** Auto-execute if policy allows
- **Low confidence (< 0.5):** Automatically route to CONFIRM policy
- **Invalid/unknown:** Reject completely

### Deterministic Execution

- No ambiguity in tool call interpretation
- No guessing or hallucination
- Invalid outputs safely ignored
- All execution through ExecutionEngine

### Validation Gates

1. **Parser gate:** Only valid JSON structures become tool calls
2. **Registry gate:** Only registered tools are accepted
3. **Schema gate:** Arguments must be valid dicts
4. **Serialization gate:** Arguments must be JSON-serializable
5. **Policy gate:** Final allow/confirm/deny decision

## Testing

Run the parser tests:
```bash
python test_tool_parser.py
```

Tests cover:
- Pure JSON single/batch/list formats
- JSON in code blocks
- Natural language (no tool calls)
- Empty input
- Malformed JSON
- Unknown tools (rejection)

## API Changes

### GenerateResponse

Added field:
- `validation_errors`: Optional[List[str]]

Returned when tool calls fail validation (not executed).

## Files Modified

1. `backend/core/tool_protocol.py` - Enhanced schema with confidence
2. `backend/core/tool_parser.py` - New: robust parser
3. `backend/providers/lmstudio.py` - Normalized output through parser
4. `backend/executor/engine.py` - Added validation gate and logging
5. `backend/executor/policy.py` - Added confidence handling
6. `backend/app.py` - Wired parser to provider, added logging

## Backward Compatibility

- All existing endpoints unchanged
- Existing tools work without modification
- Policy rules unchanged (except confidence addition)
- Frontend can optionally display validation_errors

## Future Enhancements

This stabilization enables:
- Multi-step tool orchestration
- WebSocket streaming of tool execution
- Autonomous agents with reliable tool use
- Additional providers (ChatGPT, Claude, Codex)
- Complex workflow automation

## Verification

✅ All imports successful
✅ Parser tests pass (8/8)
✅ FastAPI app initializes correctly
✅ Registered tools: ['git_push', 'git_add', 'read_file', 'git_commit', 'write_file', 'git_status']
✅ Logging configured and working

## Conclusion

The tool execution contract is now **strict, reliable, and deterministic**. LM Studio models will either:
- Produce valid, validated, policy-approved tool calls that execute reliably, OR
- Have their outputs safely treated as plain text

No malformed tool output will ever reach the execution layer.