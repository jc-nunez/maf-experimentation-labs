# A8 Quality

Map: [platform map](../map.md) · Maturity: **Partial** · Review: [2026-10-10](../../reviews/2026-10-10-state-review.md)

## Purpose
Confidence that things work: tests, validation, diagnostics, evals, CI.

## Current state
| Capability | Python / where | Status | .NET |
|---|---|---|---|
| Offline tests on mock | `*/tests/` | Built (49 tests) |  |
| Live tests (`-m live`) | `test_live.py` | Built |  |
| `mafx validate` | `main.py` | Partial (.NET not built) |  |
| `mafx doctor` | `main.py` | Built |  |
| Evals |  | Planned |  |
| CI |  | Missing |  |

## Gaps
- No evals
- No CI
- No tests for interrupt, .NET protocol edge cases, workflow failure exit codes

## Features
Requirements live at feature level: `docs/platform/features/<area>-<feature>.md` (created when we drill in).

| ID | Feature | What it does | Python | .NET | Requirements |
|---|---|---|---|---|---|
| A8.F1 | Offline tests | mock-provider tests per component | Built | Partial | not yet |
| A8.F2 | Live tests | `-m live` against a real endpoint | Built | Partial | not yet |
| A8.F3 | Validation | `mafx validate` builds components | Partial | Missing (files only) | not yet |
| A8.F4 | Evals | datasets, suites, baselines, reports | Planned | Planned | not yet |
| A8.F5 | CI | checks on every push | Missing | Missing | not yet |

## Items
| ID | Item | Stage |
|---|---|---|
| | | |

## Decisions
| ID | Decision | Date | Item |
|---|---|---|---|
| | | | |
