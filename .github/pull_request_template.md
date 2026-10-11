<!-- Title: Conventional Commits, e.g. feat(mail): add read-only triage agent for outlook.com
     Concise: fits one screen (~40 lines plus the Map). Background <= 3 lines. Scope, Review order <= 7 rows.
     Decisions, Risks <= 3 each. No filler, no restating the diff. Delete empty sections.
     Tables and diagrams over prose; every claim points to a file. -->

## Background
<!-- Why this change exists, 1 to 3 lines. Link the bet or slice. -->
Refs: bet-NNN/sNN

## Scope
| In | Out |
|---|---|
| | |

## Approach

### Map
<!-- ASCII diagram of the feature: components or classes, file paths, calls and data flow.
     Mark [NEW] and [CHANGED]; unmarked boxes are context. -->
```
 ┌ [NEW] path/to/module.py ─────────┐        ┌ [CHANGED] path/to/other.py ┐
 │ ClassName                         │ ─────► │ function()                 │
 │  + method(args) -> Result         │        └────────────────────────────┘
 └───────────────────────────────────┘
```

### Review order
| # | File | Look at |
|---|---|---|
| 1 | | |

### Decisions and trade-offs
| Decision | Chosen | Alternative | Why |
|---|---|---|---|
| | | | |

### Risks and follow-ups
-

## Verify
| Check | Command | Expected |
|---|---|---|
| Demo | | |
| Checks | `uv run ruff check . && uv run ruff format --check . && uv run pytest && uv run mafx validate` | all pass |
