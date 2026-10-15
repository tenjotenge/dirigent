# Architecture

## Request path

```text
React/Tauri UI -> FastAPI backend -> selected provider adapter -> model/API
                      |                     |
                      |                     +-> normalized text + metadata
                      v
              execution engine -> tool-call parser -> policy -> local tools
                      |
                      v
              SQLite conversation archive -> encrypted Parquet .dpa transfer
```

The frontend is in `frontend/src/`; `frontend/src/App.tsx` coordinates chat,
provider/model selection, confirmation, and archive navigation.
`frontend/src/api/client.ts` contains the backend calls. Tauri wiring is in
`frontend/src-tauri/`.

`backend/app.py` owns HTTP endpoints and chooses one `ExecutionEngine` per
direct-model provider. `backend/core/interfaces.py` defines the provider
contract. `backend/providers/` holds LM Studio, ChatGPT, Claude, and Perplexity
adapters. `backend/providers/catalog.py` distinguishes these direct routes
from Cursor, Devin, and OpenClaw, whose external-agent routes are disabled.

`backend/executor/engine.py` validates model-suggested tool calls, passes them
through `backend/executor/policy.py`, and executes only automatically allowed
calls. Reads and Git status can run without confirmation; writes and Git
mutations require it. Explicit user-triggered tool endpoints are a separate
path and should not be described as having gone through the model-call policy.
The [tool execution contract](../TOOL_EXECUTION_CONTRACT.md) is the detailed
reference for this boundary.

`backend/archive.py` stores conversations, messages, and runs in local SQLite.
It records provider/model, status, error, timing, tool results, and metadata;
reported reasoning effort is retained when provided. `backend/archive_parquet.py`
serializes portable Parquet and wraps it in passphrase-derived AES-GCM
encryption for `.dpa` export/import. Export/import is for consolidation, not a
live cross-machine synchronization service.

`backend/prompt_files.py` validates small UTF-8 text attachments and includes
their contents in the selected direct provider's prompt. The original file
content is stored in user-message metadata, preserved by `.dpa` transfer, and
downloadable when reopening a conversation. This is text inclusion, not a
provider-native upload or a generated-file retrieval path.

## Credentials and trust boundaries

ChatGPT uses the local OAuth flow in `backend/openai_auth.py`. Claude and
Perplexity use API keys from the environment or the local credential store in
`backend/provider_credentials.py`; Cursor and Devin keys can be saved there
but do not enable generation routes. A configured flag means credential
presence, not successful authentication. Do not expose tokens to the frontend,
logs, archives, or documentation.

Perplexity currently calls the Agent API with provider-hosted tools disabled,
including web search. This keeps the direct-model route distinct from an
external-agent run. File transfer, remote tool invocation, and artifact
retrieval will need explicit security, consent, provenance, and archive
semantics before being added.

## Launch paths

`run_dirigent.bat` / `run_dirigent.ps1` provide Windows startup;
`linux-v1/run_dirigent.sh` is the isolated Linux development launcher. Both
locate the project, use `.venv`, reuse a healthy backend or start one, poll
`/health`, and launch the frontend only when healthy. Linux launcher runtime
files live under `linux-v1/runtime/`; Windows backend logs live under `logs/`.
