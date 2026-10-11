# A1 Core runtime

Map: [platform map](../map.md) · Maturity: **Partial** · Review: [2026-10-10](../../reviews/2026-10-10-state-review.md)

## Purpose
Builds components from manifests and runs turns: builders, runners, approvals relay, sessions, memory scope, effort.

## Current state
| Capability | Python / where | Status | .NET |
|---|---|---|---|
| Component builders (python, declarative) | `libs/python/maf_labs_host/src/maf_labs_host/runtime.py` | Built | n/a (code registration) |
| Agent runner | `runner.py` AgentRunner | Built | Built (`MafLabsHost.cs` AgentRunner) |
| Workflow runner | `runner.py` WorkflowRunner | Partial | Missing |
| Approvals relay | `approvals.py` | Built | Partial |
| Turn cancellation | task cancel only | Partial | Missing |
| Sessions: reset | `Runner.reset` | Built | Built |
| Sessions: save / resume |  | Missing | Missing |
| Memory scope (session / persistent) | factory code | Missing | Missing |

## Gaps
- Turn cancellation (F1)
- Workflow `ok` flag on failure events (F2)
- Stale approvals after a new message (F3)
- Workflow approvals and multi-request `request_info`
- Sessions: save, resume, storage interface
- Configurable memory scope (F5)

## Features
Requirements live at feature level: `docs/platform/features/<area>-<feature>.md` (created when we drill in).

| ID | Feature | What it does | Python | .NET | Requirements |
|---|---|---|---|---|---|
| A1.F1 | Component build | manifest entry → agent, workflow or tool object | Built | Missing (no manifest loading) | not yet |
| A1.F2 | Agent turns | run a turn, stream updates, translate to events | Built | Built | not yet |
| A1.F3 | Workflow turns | run workflows, request_info, outputs | Partial | Missing | not yet |
| A1.F4 | Tool approvals | pause, relay decisions, continue the turn | Built | Partial | not yet |
| A1.F5 | Turn cancellation | stop a running turn cleanly | Partial | Missing | not yet |
| A1.F6 | Sessions | reset, save, resume, storage interface | Partial | Partial | not yet |
| A1.F7 | Memory scope | session or persistent memory per agent | Missing | Missing | not yet |
| A1.F8 | Reasoning effort | manifest, flag, per-session override | Built | Built | not yet |

## Items
| ID | Item | Stage |
|---|---|---|
| | | |

## Decisions
| ID | Decision | Date | Item |
|---|---|---|---|
| | | | |
