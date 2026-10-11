# A4 Model access

Map: [platform map](../map.md) · Maturity: **Built** · Review: [2026-10-10](../../reviews/2026-10-10-state-review.md)

## Purpose
Provider selection and chat client creation; provider-specific compatibility fixes.

## Current state
| Capability | Python / where | Status | .NET |
|---|---|---|---|
| sglang (Responses, Chat fallback) | `providers.py` | Built | Built |
| openai | `providers.py` | Built | Built |
| azure-openai | `providers.py` | Built (key, Entra ID) | Partial (key only) |
| foundry | `providers.py` | Built | Missing |
| mock | `mock.py` | Built | Built (`MockChatClient.cs`) |

## Gaps
- .NET foundry provider
- .NET azure-openai Entra ID
- `minimal` effort mapped to low in .NET

## Features
Requirements live at feature level: `docs/platform/features/<area>-<feature>.md` (created when we drill in).

| ID | Feature | What it does | Python | .NET | Requirements |
|---|---|---|---|---|---|
| A4.F1 | Provider resolution | flag, env, workspace default; config errors | Built | Built | not yet |
| A4.F2 | Self-hosted compatibility | SGLang Responses quirks, Chat fallback | Built | Built | not yet |
| A4.F3 | Cloud providers | openai, azure-openai, foundry | Built | Partial | not yet |
| A4.F4 | Mock provider | deterministic offline client | Built | Built | not yet |

## Items
| ID | Item | Stage |
|---|---|---|
| | | |

## Decisions
| ID | Decision | Date | Item |
|---|---|---|---|
| | | | |
