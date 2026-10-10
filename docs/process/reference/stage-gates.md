# Working agreement: requirements first

Purpose: finish what we start. Every change moves through the same stages, and every stage ends at a human gate.
Nothing in a stage starts until the previous gate is passed.

## Roles
- **Owner (Jean):** brings the need, answers questions, approves gates, implements plan tasks (directly or through Claude Code).
- **Technical assistant (Claude):** turns the need into requirements, challenges gaps, writes the design and the plan,
  and reviews implementation against the acceptance criteria when asked.

## Stages and gates

| Stage | Artifact | Gate | Exit criteria |
|---|---|---|---|
| 0. Intake | one row in `docs/work/README.md` (Backlog) | none | problem stated in one sentence; sized to fit rule 3 or split |
| 1. Requirements | feature files (`docs/platform/features/`) + item scope (`docs/work/NNN-slug/requirements.md`) | **G1** owner approves | every requirement has an ID, a priority and an acceptance check; non-goals listed; no open questions left (answered or explicitly deferred) |
| 2. Design | `design.md` | **G2** owner approves | every Must requirement traces to a design section; interfaces specified exactly (manifest keys, CLI flags, protocol events, file layout, APIs); Python/.NET parity decided; decisions recorded |
| 3. Plan | `plan.md` | **G3** owner approves | tasks ordered, each small (half a day or less), each with a runnable done check and the requirement IDs it serves |
| 4. Execute | commits | **G4** per task: its done check passes | task marked done in `plan.md` |
| 5. Close | status `Done` on the board | **G5** owner confirms | all acceptance checks pass; Definition of Done met; three-line retro written in `plan.md` |

A gate is passed when the artifact's front matter says so, for example `status: G1-approved 2026-10-10`.

## Rules for finishing
1. **One active item.** Only one item is in Requirements, Design, Plan or Execute at a time. New ideas go to the Backlog.
2. **Scope freezes at G1.** A new need found later becomes a Backlog item. Reopen G1 only if an acceptance criterion
   cannot be met without it, and record the change in the requirements change log.
3. **Small slices.** An item fits in 3 to 8 plan tasks. Bigger items are split at Intake.
4. **Testable or it is not a requirement.** Every acceptance criterion is a pytest, a command with its expected
   result, or numbered manual steps with an expected result.
5. **Decisions are written down.** Any choice between options goes in `design.md` under Decisions, with the rationale.
6. **Stop rule.** A task that takes twice its estimate stops; we re-plan before continuing.
7. **Done means done.** No item closes with failing checks, missing docs or an unstated parity gap.

## Definition of Done (every item)
- The checks in `AGENTS.md` pass: `ruff check`, `ruff format --check`, `pytest` (offline), `mafx validate`,
  and `dotnet build maf-labs.slnx` when .NET code changed.
- New behaviour has an offline test on the `mock` provider; live-only behaviour has a `-m live` test.
- Docs touched by the change are updated (`README.md`, `docs/*.md`). Any change to arguments or events updates
  `docs/host-protocol.md` in the same commit.
- Python/.NET parity is either implemented or written as a known gap in the design.
- Every task in `plan.md` is checked off and every acceptance check is recorded as passing.

## Session protocol
State lives in `docs/STATUS.md`. A session never starts from memory or chat history; it starts from that file.

Every session follows OPEN, WORK, CLOSE:
```
 OPEN   Focus: <area> / <item> @ <stage>
 WORK   tangent? one line in docs/work/parking-lot.md, then back to the focus
 CLOSE  update docs/STATUS.md (position, focus, next actions, decisions, one log row); report what moved and the next gate
```
Navigation is top down:
```
 L0 Map      docs/platform/map.md                    what exists, how mature
 L1 Area     docs/platform/areas/aNN-*.md            why: scope, state, features
 L2 Feature  docs/platform/features/aNN-fN-*.md      what: requirements + acceptance checks
 L3 Item     docs/work/NNN-slug/                     when: selected requirements, design, plan
 L4 Task     rows in plan.md                         how: one done check each
```

1. You describe the need in your own words (bullets are fine).
2. I draft `requirements.md` with at most five open questions and proposed non-goals.
3. You answer and approve G1.
4. I draft `design.md`, you approve G2. I draft `plan.md`, you approve G3.
5. You implement the plan task by task. I review diffs against the plan and acceptance criteria on request.
6. We close the item together and pick the next one from the Backlog.

## Layout
```
docs/STATUS.md                    start here: position, focus, next actions, decisions, session log
docs/process/README.md            this agreement
docs/process/templates/           feature.md, requirements.md (item scope), design.md, plan.md
docs/platform/map.md              L0: the platform map
docs/platform/areas/              L1: one file per area (A1 to A10)
docs/platform/features/           L2: one file per feature (requirements)
docs/work/README.md               the board: Active, Backlog, Done
docs/work/parking-lot.md          tangents captured during sessions
docs/work/NNN-slug/               one folder per item (requirements.md, design.md, plan.md)
docs/reviews/                     point-in-time reviews that feed the Backlog
```
