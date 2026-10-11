# A7 Observability

Map: [platform map](../map.md) · Maturity: **Partial** · Review: [2026-10-10](../../reviews/2026-10-10-state-review.md)

## Purpose
Seeing what agents did: traces, metrics, distributed telemetry.

## Current state
| Capability | Python / where | Status | .NET |
|---|---|---|---|
| Per-run trace `trace.jsonl` | `trace.py` | Built | via mafx |
| Turn usage and timing | events | Built | Built |
| OpenTelemetry export |  | Planned | Planned |
| Aspire Dashboard / Jaeger |  | Planned | Planned |

## Gaps
- No OpenTelemetry
- Standalone .NET runs are not traced
- No cross-run metrics

## Features
Requirements live at feature level: `docs/platform/features/<area>-<feature>.md` (created when we drill in).

| ID | Feature | What it does | Python | .NET | Requirements |
|---|---|---|---|---|---|
| A7.F1 | Run traces | per-run `trace.jsonl` | Built | via mafx | not yet |
| A7.F2 | Usage and timing | tokens, model calls, durations per turn | Built | Built | not yet |
| A7.F3 | OpenTelemetry export | spans and metrics over OTLP | Planned | Planned | not yet |
| A7.F4 | Dashboards | Aspire Dashboard or Jaeger wiring | Planned | Planned | not yet |

## Items
| ID | Item | Stage |
|---|---|---|
| | | |

## Decisions
| ID | Decision | Date | Item |
|---|---|---|---|
| | | | |
