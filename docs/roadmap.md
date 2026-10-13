# Roadmap

This is an ordered implementation direction, not a claim that every provider
offers the same API or that all work has been scheduled.

1. **Validate the direct routes end to end.** Test account/key setup, model
   discovery, requests, error handling, and archive metadata with real
   user-authorized accounts on the supported OSes. Record verified service,
   model, and effort behavior rather than inferring it from test doubles.
2. **Introduce a provider-neutral attachment and artifact contract.** Define
   file size/type limits, consent, transport, storage, provenance, failure
   states, and how imported/exported conversations retain file references.
   Then add UI upload/download and one provider implementation before
   generalizing. The present `.dpa` import picker is not this feature.
3. **Build an external-agent run abstraction.** Sessions need creation,
   polling/streaming, cancellation, approvals, tool/action visibility, output
   files, and archive linkage. Integrate Cursor, Devin, and OpenClaw only as
   their official contracts and trust boundaries allow. Do not insert them
   into `/generate` as if they were plain text models.
4. **Make archive consolidation robust for multi-agent use.** Preserve
   provider-specific metadata and artifacts, define conflict/version rules,
   retention and deletion policy, and test large encrypted transfers across
   installations. Investigate incremental sync only after portable import is
   dependable.
5. **Polish the universal launcher and UI.** Keep Windows and Linux launch
   contracts aligned, test failure/reuse/shutdown paths on real machines, and
   consider macOS and packaging after the development paths are stable.

Cross-cutting acceptance criteria: no silent side effects, no token leakage,
truthful capability/status displays, clear cost/usage reporting where a
provider supplies it, and tests for incomplete/error responses. Provider
pricing and API terms change; verify them when implementing each connector.
