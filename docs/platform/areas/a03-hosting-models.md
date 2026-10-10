# A3 Hosting models

Map: [platform map](../map.md) · Maturity: **Partial** · Review: [2026-10-10](../../reviews/2026-10-10-state-review.md)

## Purpose
How the same core runtime is exposed: in-process, stdio host, and later an HTTP service and containers.

## Current state
| Capability | Python / where | Status | .NET |
|---|---|---|---|
| In-process (mafx + Python host) | `cli/src/mafx/targets.py` | Built | n/a |
| Stdio host (JSONL) | `cli.py` serve_stdio | Built | Built |
| Standalone CLI (`-p`, interactive) | `cli.py` | Built | Built |
| HTTP service |  | Planned | Planned |
| Container packaging |  | Missing | Missing |

## Gaps
- Surfaces live next to the core (`cli.py`, `MafLabsHost.cs`); no clean seam for new hosting models
- No HTTP service hosting model
- No container image or packaging

## Features
Requirements live at feature level: `docs/platform/features/<area>-<feature>.md` (created when we drill in).

| ID | Feature | What it does | Python | .NET | Requirements |
|---|---|---|---|---|---|
| A3.F1 | In-process hosting | mafx runs the core in its own process | Built | n/a | not yet |
| A3.F2 | Stdio host | JSONL over stdio | Built | Built | not yet |
| A3.F3 | Standalone CLI host | `-p` and interactive without mafx | Built | Built | not yet |
| A3.F4 | Core / surface separation | new hosting models without touching the core | Missing | Missing | not yet |
| A3.F5 | HTTP service host | agents as a service (HTTP, streaming) | Planned | Planned | not yet |
| A3.F6 | Container packaging | image per project or per agent | Missing | Missing | not yet |
| A3.F7 | Triggers | scheduled and event-triggered runs, no person present | Missing | Missing | not yet |

## Items
| ID | Item | Stage |
|---|---|---|
| | | |

## Decisions
| ID | Decision | Date | Item |
|---|---|---|---|
| | | | |
