# Dirigent project docs

These are the maintained handoff notes for Dirigent. They follow the useful
purpose / architecture / current-state / next-work pattern used by neighboring
projects, but describe this repository rather than copying their assumptions.
Last reviewed against `main`: 2026-10-14.

Read in this order when joining the project:

1. [Vision](vision.md) — the product goal and boundaries.
2. [Current state](current_state.md) — what works, what is only scaffolded, and what remains unverified.
3. [Architecture](architecture.md) — the implementation and trust boundaries.
4. [Roadmap](roadmap.md) — the next integration milestones.

For changes, also consult [decisions](decisions.md) and the
[handoff checklist](handoff.md). The root [README](../README.md) has setup and
API examples; [Linux launcher notes](../linux-v1/README.md),
[tool execution contract](../TOOL_EXECUTION_CONTRACT.md), and
[inference hardening notes](../LONG_RUNNING_INFERENCE_HARDENING.md) cover
specialized details.

Keep this directory free of credentials, exported conversations, local paths
that identify a user, and machine-specific runtime logs. Update current state
and roadmap when a capability changes; an implemented adapter is not the same
as a live-tested service connection.
