# Documentation

Dirigent's documentation separates product scope, implemented behavior, and planned work. Start with the [project README](../README.md) for setup and a product overview.

| Document | Contents |
| --- | --- |
| [Vision and scope](vision.md) | Product goals and boundaries |
| [Current state](current_state.md) | Implemented capabilities and verification limits |
| [Architecture](architecture.md) | Components, data flow, and trust boundaries |
| [Roadmap](roadmap.md) | Planned integration milestones |
| [Decisions](decisions.md) | Rationale for current design choices |
| [Contributor guide](handoff.md) | Code entry points and change checklist |

Specialized references: [Linux launcher](../linux-v1/README.md), [tool execution contract](../TOOL_EXECUTION_CONTRACT.md), and [long-running inference](../LONG_RUNNING_INFERENCE_HARDENING.md).

Documentation should reflect the tracked code and distinguish an implemented adapter from a connection verified with a live service. Do not commit credentials, conversation exports, personal paths, or runtime logs.
