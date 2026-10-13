# Current state

Reviewed 2026-10-14 against the tracked code. “Implemented” below means the
route and offline tests exist, not that a paid/live provider account was
verified on this machine.

| Area | Current state | Important limit |
| --- | --- | --- |
| Windows startup | One-click batch/PowerShell launcher, health polling, backend reuse/logging | Windows runtime still needs on-machine validation |
| Linux startup | `linux-v1` launcher and isolated smoke test | Development launch path, not a packaged Linux release |
| LM Studio | Local direct-model adapter | Requires a reachable local LM Studio server |
| ChatGPT | Account connection flow and direct generation route | Account entitlement/connectivity need live verification |
| Claude | API-key credential UI and Messages API adapter | An API key is separate from a Claude subscription |
| Perplexity | API-key credential UI, Agent API model route, resolved model/usage archive metadata | Provider-hosted tools and web search are disabled; live key not tested here |
| Cursor / Devin | Credential storage and capability catalog | No session, prompt, or artifact adapter yet |
| OpenClaw | Gateway configuration detection and capability catalog | No enabled gateway execution route |
| Conversation archive | Local SQLite, search/reopen, provider/model/effort metadata, encrypted `.dpa` export/import | No live sync, retention policy, or remote-session ingestion |
| Files | Local read/write tools and markdown rewrite endpoint | No general attachment upload to providers or produced-file download flow |

The current UI selects a provider and model and sends text prompts through
`/generate`. It can resume a Dirigent archive conversation by ID. Provider
models are fetched through `/models?provider=...`; the capability catalog is
available at `/providers/capabilities`. The archive records actual provider
metadata when adapters return it; effort may remain unknown if a provider does
not report it. The main chat input is text-only. The Archive screen's file
picker is for `.dpa` imports, not prompt attachments.

Current offline verification commands from the repository root:

```bash
XDG_CONFIG_HOME=$(mktemp -d) .venv/bin/python -m unittest discover -q
cd frontend && npm run build
bash linux-v1/tests/test_launcher.sh
```

The temporary config directory keeps tests from touching a real local archive.
The Linux smoke test uses port 8000 briefly and should not be run while a
healthy Dirigent backend occupies it. These checks do not substitute for
Windows UI, account OAuth, or paid API end-to-end tests.
