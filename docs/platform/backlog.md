# Work board

Process: `docs/process/README.md`. One item active at a time.

## Active
| ID | Item | Stage | Next gate |
|---|---|---|---|
| | | | |

## Backlog
Ordered by the platform intent in `docs/platform/map.md` (core and hosting separate, full .NET parity).

| ID | Item | Source | Notes |
|---|---|---|---|
| | Event stream contract v1: protocol version, JSON Schema, cancel message, contract tests run against both hosts | map implications 2, 3 | foundation for services, parity, evals, viewer |
| | Host reliability: cancellation, workflow `ok` flag, stale approvals, error handling (F1, F2, F3, F6) | review 2026-10-10 | can merge with the contract item |
| | Core and hosting surface split (Python and .NET) | map implication 1 | prepares the HTTP service |
| | .NET parity: workflows, manifest tools and shared tools, `--allow-tool`, error handling (F4) | map implication 3 | |
| | Sessions: save, resume, storage interface | map implication 4 | |
| | Configurable memory scope (F5) | map implication 5 | |
| | Telemetry: OpenTelemetry, Aspire Dashboard, `mafx devui` | roadmap step 2 | |
| | Evals: datasets, suites, baselines, `mafx eval` | roadmap step 3 | |
| | HTTP service hosting model | platform intent | |
| | Viewer: `mafx web` | roadmap step 4 | |

## Done
| ID | Item | Closed |
|---|---|---|
