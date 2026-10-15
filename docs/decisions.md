# Decisions and rationale

These are decisions visible in the code and project history. Revisit them if
requirements change; do not treat them as universal rules for other projects.

| Decision | Reason / consequence |
| --- | --- |
| Separate provider, executor, and tool layers | Models can change without granting them direct filesystem or Git control. The execution engine and policy remain the local action gate. |
| Keep external agents cataloged but not routed | Cursor, Devin, and OpenClaw can act outside the local tool pipeline. A stored key or gateway URL is not enough to claim safe session integration. |
| Keep platform launchers separate | Windows one-click startup and `linux-v1` development startup share a health-based sequence without forcing platform-specific behavior into one script. |
| Store the rolling archive locally in SQLite | Conversations remain searchable and independent of a provider service. Archive metadata captures service, model, and reported effort when available. |
| Export encrypted Parquet in `.dpa` | Parquet supplies a portable structured payload; passphrase-derived AES-GCM, not Parquet's binary encoding, makes exports confidential and tamper-evident. |
| Distinguish subscription login from API keys | ChatGPT account connection has its own OAuth path. Claude and Perplexity direct routes use their respective API keys; saved credentials are not proof of working access. |
| Disable Perplexity-hosted tools on its direct route | Its Agent API can invoke search and other provider-side tools. The current adapter deliberately requests none until those actions can be represented honestly in the UI and archive. |
| Start file routing with bounded UTF-8 text inclusion | This works across the current direct-model adapters without pretending to support provider-native uploads. Small limits curb accidental token overload; original content is kept in message metadata for archive transfer and download. |

Review relevant code and tests before changing a decision. For example, a new
file-capable provider may require a new response/artifact contract, not simply
another string-returning `send()` method.
