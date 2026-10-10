# A9 Infrastructure

Map: [platform map](../map.md) · Maturity: **Built** · Review: [2026-10-10](../../reviews/2026-10-10-state-review.md)

## Purpose
Services agents depend on and local run data.

## Current state
| Capability | Python / where | Status | .NET |
|---|---|---|---|
| Model endpoint (SGLang, external) | `.env` | Built |  |
| SearXNG | `infra/searxng` | Built |  |
| Run data `.mafx/` | traces, history, memory, work | Partial |  |
| Telemetry backend |  | Planned |  |

## Gaps
- No retention or cleanup for `.mafx/`
- Stray `projects/harness-lab/.mafx/` (F11)

## Features
Requirements live at feature level: `docs/platform/features/<area>-<feature>.md` (created when we drill in).

| ID | Feature | What it does | Python | .NET | Requirements |
|---|---|---|---|---|---|
| A9.F1 | Model endpoint config | `.env`, doctor checks | Built | Built | not yet |
| A9.F2 | Local services | docker compose services (SearXNG) | Built | n/a | not yet |
| A9.F3 | Run data store | `.mafx/` layout and retention | Partial | Partial | not yet |
| A9.F4 | Telemetry backend | local collector and dashboard | Planned | n/a | not yet |
| A9.F5 | Domain isolation | data, secrets and run data separated per domain (personal, Trossitec, lab) | Missing | Missing | not yet |

## Items
| ID | Item | Stage |
|---|---|---|
| | | |

## Decisions
| ID | Decision | Date | Item |
|---|---|---|---|
| | | | |
