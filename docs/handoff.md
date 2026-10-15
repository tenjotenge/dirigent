# Handoff for the next contributor or agent

Start with [vision](vision.md), [current state](current_state.md), and
[architecture](architecture.md). Then inspect the exact code you will change;
these notes are a map, not a substitute for the implementation.

Useful entry points:

- Backend routes and archive wiring: `backend/app.py`
- Provider contract and adapters: `backend/core/interfaces.py`, `backend/providers/`
- Credential sources and capability labels: `backend/provider_credentials.py`,
  `backend/openai_auth.py`, `backend/providers/catalog.py`
- Local action gate: `backend/executor/engine.py`, `backend/executor/policy.py`
- Archive and transfer: `backend/archive.py`, `backend/archive_parquet.py`
- UI flow and API types: `frontend/src/App.tsx`, `frontend/src/api/client.ts`
- Launchers: `run_dirigent.ps1`, `run_dirigent.bat`, `linux-v1/`
- Existing tests: `test_archive*.py`, `test_provider_connectors.py`,
  `test_prompt_files.py`, `linux-v1/tests/test_launcher.sh`

Before implementing a connector, determine whether it is a direct-model API
or an external agent, what authentication the service officially supports,
whether it can act outside Dirigent, and how its model/effort/usage and files
will enter the archive. Never equate “credential saved” with “connected” or
“response received” with “all artifacts captured.” Do not import browser
sessions or private client tokens from other applications.

For a scoped change: check `git status`, read the relevant interface and
tests, update the code and this documentation together, run offline tests and
the frontend build as appropriate, then report which live-provider/OS paths
remain unverified. Do not place real credentials or conversation exports in
Git. Small UTF-8 prompt attachments are now supported, but provider-native
binary input and output-file retrieval remain product gaps, followed by honest
external-agent session routing; see
[roadmap](roadmap.md).
