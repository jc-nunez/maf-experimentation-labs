# A2 Contracts

Map: [platform map](../map.md) · Maturity: **Partial** · Review: [2026-10-10](../../reviews/2026-10-10-state-review.md)

## Purpose
The agreements every layer depends on. Experience, hosting models, observability and evals consume these; they change only through a versioned process.

## Current state
| Capability | Python / where | Status | .NET |
|---|---|---|---|
| Workspace marker `maf-labs.yaml` | `workspace.py` | Built | Built (`Env.cs`) |
| Project manifest `project.yaml` | `docs/manifest.md`, `manifest.py` | Built | n/a |
| Host arguments | `docs/host-protocol.md`, `cli.py` | Built | Partial (no `--allow-tool`) |
| Stdio messages (in) | `cli.py` serve_stdio | Built | Partial (error handling differs) |
| Event stream (out) | `events.py` | Built | Built (`Events.cs`) |
| Trace file `trace.jsonl` | `trace.py` | Built | via mafx |
| Factory signatures, `HostContext` | `docs/manifest.md` | Built | n/a |
| Protocol version |  | Missing | Missing |
| Machine-readable schemas (JSON Schema) |  | Missing | Missing |
| Contract tests across hosts |  | Missing | Missing |

## Gaps
- No protocol version: clients cannot detect incompatible hosts
- No JSON Schema for events, stdio messages or the manifest
- No `cancel` message (root cause of F1)
- Divergent edge-case behaviour between hosts (F4)
- Transport is implicit (stdio only); services will need HTTP/SSE or WebSocket
- Event fields are documented in a table, not validated in tests

## Features
Requirements live at feature level: `docs/platform/features/<area>-<feature>.md` (created when we drill in).

| ID | Feature | What it does | Python | .NET | Requirements |
|---|---|---|---|---|---|
| A2.F1 | Manifest contract (C1) | schema for `project.yaml` | Partial (Pydantic) | Missing | not yet |
| A2.F2 | Host input contract (C2) | host arguments and stdio messages in | Partial (docs) | Partial | not yet |
| A2.F3 | Event stream contract (C3) | events a host emits | Partial (docs) | Partial | not yet |
| A2.F4 | Trace contract (C4) | `trace.jsonl` records | Partial (docs) | n/a (mafx records) | not yet |
| A2.F5 | Versioning | protocol major.minor, compatibility rules | Missing | Missing | not yet |
| A2.F6 | Conformance suite | shared scenarios run against both hosts | Missing | Missing | not yet |

## Items
| ID | Item | Stage |
|---|---|---|
| | | |

## Decisions
| ID | Decision | Date | Item |
|---|---|---|---|
| | | | |
