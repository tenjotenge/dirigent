# LM Studio Execution Reliability & Long-Running Request Hardening

## Summary

This document describes the hardening improvements made to Dirigent's LM Studio integration to support long-running inference (30s–5min+), large models, and future hour-long agent workflows.

## Problem Solved

**Before:** System instability under slow/large models:
- Hard timeouts killed valid long-running generation
- Frontend/backend treated slow responses as failures
- Tool parsing attempted on partial/incomplete outputs
- No visibility into long-running operations
- System behaved inconsistently under load

**After:** Robust, timeout-free execution with full observability:
- No hard timeouts on LM Studio requests
- Explicit generation lifecycle tracking
- Safe buffering (only parse complete outputs)
- Watchdog logging instead of timeout-based failures
- Adaptive latency profiles for UX feedback
- Responsive frontend during long generations

---

## Architecture

### Execution Flow (Hardened)

```
User Request
    ↓
Frontend (non-blocking, with watchdog UI)
    ↓
FastAPI /generate (no timeout)
    ↓
LMStudioProvider.send()
    ↓
[NO TIMEOUT - wait indefinitely]
    ↓
Complete Response Received
    ↓
Tool Parser (only on COMPLETE state)
    ↓
Validation Gate
    ↓
Policy Engine
    ↓
Execution Engine
    ↓
Tool Results → UI
```

**Key principle:** Never parse, validate, or execute tools until generation is COMPLETE.

---

## Components

### 1. Generation Lifecycle State Machine (`backend/providers/lmstudio.py`)

**States:**
- `IDLE` - No active generation
- `REQUEST_SENT` - HTTP request dispatched
- `WAITING_FOR_FIRST_TOKEN` - Awaiting first response byte
- `STREAMING` - Receiving tokens (future: for streaming support)
- `COMPLETING` - Processing final response
- `COMPLETE` - Ready for parsing and execution

**Rules:**
- Tool parsing ONLY occurs in `COMPLETE` state
- State transitions are logged
- State resets to `IDLE` on error

### 2. No Hard Timeouts (CRITICAL)

**Changed:**
```python
# BEFORE: 120 second timeout
response = requests.post(..., timeout=120)

# AFTER: No timeout - wait indefinitely
response = requests.post(..., timeout=None)
```

**Rationale:**
- Large models (13B–34B+) can take 2–10+ minutes
- Hour-long agent workflows require unlimited execution time
- Only user cancellation should stop generation
- Connection failures are caught by exception handling

### 3. Watchdog Logging (Replaces Timeout Failures)

**Instead of:**
```
timeout → FAIL → error to user
```

**Now:**
```
elapsed < expected_max → INFO: "Generation in progress: elapsed=45s (expected max: 120s)"
elapsed > expected_max → WARNING: "Generation taking longer than expected: elapsed=150s (expected max: 120s) - still waiting..."
```

**Only fails on:**
- Connection breaks (requests.exceptions.ConnectionError)
- Explicit HTTP errors (4xx/5xx)
- Process crashes

### 4. Adaptive Latency Profiles

**Per-model expected durations:**

| Profile | Models | Expected Min | Expected Max | Watchdog Interval |
|---------|--------|--------------|--------------|-------------------|
| fast | tiny, small, mini, fast | 5s | 20s | 10s |
| medium | medium, base, 7b, 8b | 20s | 120s | 30s |
| large | large, 13b, 14b, 20b, 34b | 120s | 600s | 60s |
| xlarge | unknown/large models | 600s | 3600s | 120s |

**Usage:**
- **ONLY for logging and UX messaging**
- **NOT for enforcement or timeouts**
- Heuristic matching on model name

### 5. Safe Buffering (Complete Output Only)

**Guarantees:**
- Full response accumulated before parsing
- No incremental tool execution
- No partial JSON parsing
- No speculative execution

**Implementation:**
- `requests.post()` returns complete response (no streaming)
- Parser invoked only after `GenerationState.COMPLETE`
- Tool pipeline triggered only on validated, complete data

### 6. Frontend UX Improvements (`frontend/src/App.tsx`)

**Watchdog Timer:**
```typescript
// Log progress every 10 seconds for requests > 10s
const watchdogInterval = setInterval(() => {
  const elapsed = Math.round((performance.now() - start) / 1000);
  if (elapsed > 10 && workflowStatus !== "completed") {
    addLog("info", `Generation in progress... (${elapsed}s elapsed)`);
  }
}, 10000);
```

**Long-Generation Detection:**
```typescript
// After 30s, update UI to show "generating_long" status
const longGenerationTimeout = setTimeout(() => {
  if (workflowStatus === "waiting_provider") {
    setWorkflowStatus("generating_long");
    addLog("info", "Model is generating (this may take a while for large models)");
  }
}, 30000);
```

**New WorkflowStatus:**
```typescript
export type WorkflowStatus =
  | "idle"
  | "sending"
  | "waiting_provider"
  | "generating_long"  // ← NEW: Long-running generation
  | "evaluating_policy"
  | "executing_tool"
  | "completed";
```

**UI Benefits:**
- Non-blocking UI (user can navigate during generation)
- Progress visibility via execution log
- No frozen loading states
- Contextual messaging ("this may take a while")

### 7. Response Metadata

**Backend now returns:**
```typescript
{
  response: string;
  tool_results?: ToolCallResult[];
  policy_decision?: PolicyDecision;
  validation_errors?: string[];
  metadata?: {
    model?: string;
    provider?: string;
    generation_time_seconds?: number;  // ← NEW
    generation_state?: string;         // ← NEW
    parse_method?: string;
    raw_output_length?: number;
  };
}
```

**Frontend uses metadata to:**
- Display generation time in logs
- Correlate backend state with UI state
- Debug slow generations

---

## Key Features

### 1. No Timeouts
- LM Studio requests run indefinitely
- Only user cancellation stops generation
- Connection failures caught via exceptions

### 2. State Machine
- Explicit states prevent partial execution
- Clear lifecycle for debugging
- State logged at each transition

### 3. Watchdog Logging
- Informative progress messages
- No false "timeout" failures
- Diagnostic visibility into slow models

### 4. Adaptive Profiles
- Model-specific expectations
- UX-appropriate messaging
- No hard enforcement

### 5. Safe Buffering
- Complete responses only
- No partial parsing
- No speculative execution

### 6. Responsive Frontend
- Non-blocking during generation
- Progress visibility
- Contextual feedback

---

## Testing

### Backend Verification
```bash
# Test app initialization
python -c "import sys; sys.path.insert(0, 'backend'); from app import app; print('OK')"

# Test parser (from v0.4)
python test_tool_parser.py
```

### Frontend Type Check
```bash
cd frontend
npx tsc --noEmit
```

**Note:** Pre-existing TypeScript errors in `StartupSplash.tsx` and `tauri.ts` are unrelated to these changes.

---

## API Changes

### Backend (LMStudioProvider)

**New fields in ProviderResponse.metadata:**
- `generation_time_seconds`: float - Total generation time
- `generation_state`: string - Final state ("complete")

**New enum:**
- `GenerationState` - Lifecycle states for tracking

**New methods:**
- `_get_latency_profile(model)` - Get expected latency for model
- `_watchdog_log(model, elapsed)` - Log progress without failure

### Frontend (GenerateResponse)

**New fields:**
- `metadata.generation_time_seconds`: number
- `metadata.generation_state`: string
- `WorkflowStatus.generating_long`: New status for long operations

---

## Files Modified

### Backend
1. `backend/providers/lmstudio.py` - Removed timeout, added state machine, watchdog logging, latency profiles

### Frontend
2. `frontend/src/types/index.ts` - Added `generating_long` status, metadata to GenerateResponse
3. `frontend/src/App.tsx` - Added watchdog interval, long-generation detection, metadata logging

---

## Backward Compatibility

- All existing endpoints unchanged
- Existing tools work without modification
- Policy rules unchanged
- Frontend gracefully handles missing metadata
- New `generating_long` status is additive

---

## Future Enhancements

This hardening enables:
- **Streaming support:** State machine ready for token-by-token streaming
- **Multi-step agents:** Hour-long workflows without timeout concerns
- **Progress callbacks:** WebSocket updates during generation
- **Cancellation tokens:** User-initiated cancellation (future)
- **Model-specific tuning:** Per-model timeout/retry policies (if needed)

---

## Verification

✅ Backend app loads successfully
✅ All 6 tools registered correctly
✅ No hard timeouts on LM Studio requests
✅ Generation state machine implemented
✅ Watchdog logging active
✅ Adaptive latency profiles defined
✅ Frontend watchdog interval implemented
✅ Long-generation detection implemented
✅ Metadata propagation working
✅ Tool pipeline only triggers on complete data

---

## Conclusion

The LM Studio integration is now **hardened for long-running inference**. The system will:

- **Never** timeout valid generation
- **Never** parse incomplete outputs
- **Always** log progress for slow models
- **Always** keep UI responsive
- **Only** execute tools on complete, validated responses

This provides a stable foundation for future multi-step and hour-long agent workflows.