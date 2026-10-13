# Vision and scope

Dirigent aims to be one local launcher and workspace for communicating with
multiple AI frontends and agent architectures. The user should be able to
choose where a request goes, retain the resulting conversation and artifacts,
and switch providers without rebuilding their workflow or losing context. This
reduces dependence on any single intelligence, pricing model, or context/token
limit. Model/provider diversity is the product goal, not simply a dropdown.

The desired end-to-end path is:

```text
prompt + selected files -> chosen model or agent -> response + produced files
                                     |
                                     v
                    searchable, portable conversation archive
```

Today Dirigent is a local-first development workspace with a React/Tauri UI,
FastAPI backend, direct model routes, a guarded local tool pipeline, and a
conversation archive. It is **not yet** a universal chat/file bridge. Direct
model APIs and autonomous external agents are different integration classes:
external agents can run their own tools or create files outside Dirigent's
policy engine. Their sessions, approvals, provenance, and artifacts must be
represented explicitly before they are enabled as ordinary routes.

Product principles:

- Provider-neutral records: always retain the service, resolved model, and
  reported effort/usage when available; keep unknown fields unknown.
- User control: show the provider and any side effects, with confirmation for
  local writes and Git mutations.
- Portability: local records and encrypted export/import should make switching
  installations practical.
- Honest capability labels: a saved credential, working adapter, live-verified
  connection, and full artifact round trip are different milestones.
- Local-first operation: provider credentials and archives stay on the user's
  machine unless a chosen service call or explicit export sends data away.

Out of scope for the current implementation: silently importing sessions from
other apps, treating an API key as a consumer subscription, or letting an
external agent's tools run under the fiction that Dirigent approved them.
