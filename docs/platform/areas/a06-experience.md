# A6 Experience

Map: [platform map](../map.md) · Maturity: **Built** · Review: [2026-10-10](../../reviews/2026-10-10-state-review.md)

## Purpose
How people use the platform: mafx CLI, interactive session, renderer, scaffolding, trace replay, and later a viewer and DevUI.

## Current state
| Capability | Python / where | Status | .NET |
|---|---|---|---|
| mafx run (-p, interactive) | `cli/src/mafx/main.py`, `interactive.py` | Built |  |
| Renderer | `render.py` | Built |  |
| Scaffolding `mafx new` | `scaffold.py` | Built |  |
| validate, doctor, models, tool, trace, infra | `main.py` | Built |  |
| Viewer `mafx web` |  | Planned |  |
| DevUI `mafx devui` |  | Planned |  |

## Gaps
- Double error line on non-TTY interactive run (F6)
- `doctor` mislabels reasoning (F10)
- Viewer and DevUI not started

## Features
Requirements live at feature level: `docs/platform/features/<area>-<feature>.md` (created when we drill in).

| ID | Feature | What it does | Python | .NET | Requirements |
|---|---|---|---|---|---|
| A6.F1 | Run | `mafx run` once and interactive | Built | via stdio | not yet |
| A6.F2 | Rendering | trajectory views, escaping | Built | n/a | not yet |
| A6.F3 | Scaffolding | `mafx new` for every runtime | Built | Built | not yet |
| A6.F4 | Workspace operations | validate, doctor, models, infra | Partial | Partial | not yet |
| A6.F5 | Tool bench | `mafx tool inspect`, `tool run` | Built | Missing | not yet |
| A6.F6 | Trace replay | `mafx trace list`, `show` | Built | n/a | not yet |
| A6.F7 | Web viewer | `mafx web` | Planned | n/a | not yet |
| A6.F8 | DevUI | `mafx devui` | Planned | Planned | not yet |

## Items
| ID | Item | Stage |
|---|---|---|
| | | |

## Decisions
| ID | Decision | Date | Item |
|---|---|---|---|
| | | | |
