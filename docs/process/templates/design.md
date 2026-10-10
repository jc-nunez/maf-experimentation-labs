---
id: NNN
status: draft            # draft | G2-approved YYYY-MM-DD
requirements: requirements.md (G1-approved YYYY-MM-DD)
---
# NNN design: <title>

## Summary
<One paragraph: the approach in plain words.>

## Current state
<What exists today, with file references (path:line).>

## Approach
<How it works. Components, responsibilities, flow. Add a diagram if it helps.>

## Interfaces
Specify exactly; these are what the plan implements and the tests check.
- Manifest (`project.yaml`) keys:
- CLI (`mafx`) commands and flags:
- Host arguments and protocol messages/events (`docs/host-protocol.md`):
- Python API (`maf_labs_host`):
- .NET API (`MafLabs.Hosting`):
- Files and folders (paths, formats):
- Configuration (`.env` variables, defaults):

## Parity
| Capability | python | declarative | dotnet | Note |
|---|---|---|---|---|

## Decisions
| ID | Question | Options considered | Choice | Rationale |
|---|---|---|---|---|
| D1 | | | | |

## Risks
| Risk | Impact | Mitigation |
|---|---|---|

## Test strategy
- Offline (mock provider):
- Live (`-m live`):
- Manual:

## Traceability
| Requirement | Design section | Test |
|---|---|---|
| R1 | | |
