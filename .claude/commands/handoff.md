---
description: Claim and execute a Cowork handoff from the shared queue, then write the report back
argument-hint: "[handoff id, e.g. h002]"
---
The queue is shared by every worktree of this repo: `<main checkout>/.handoffs/` (gitignored).
Resolve it with: `QUEUE="$(cd "$(git rev-parse --path-format=absolute --git-common-dir)/.." && pwd)/.handoffs"`.

1. Read `AGENTS.md` and `docs/NOW.md`.
2. Pick the handoff:
   - `$ARGUMENTS` given: `$QUEUE/$ARGUMENTS-*.md`.
   - Otherwise: the file with `status: ready` whose `branch:` equals `git branch --show-current`.
   - None or several: list ready handoffs (id, branch, title) and stop.
3. Check: `status` is `ready` (`draft` means it is waiting; say what it waits for and stop) and the current branch equals `branch:`. If not, say what is wrong in one line and stop.
4. Claim it: `status: in-progress`, `claimed_by: <this worktree path>`, `started: <now>`.
5. Execute the Steps in order. Respect every STOP and the rules in AGENTS.md (Conventional Commits, PR template).
   Stay inside the `touches:` paths. Never merge, never force-push, never delete branches unless a step says so.
6. Problem or ambiguity: `status: blocked`, question under Report, stop.
7. Done-when met: fill the Report (commits, checks, PR URL, decisions for Jean), `status: done`,
   move the file to `$QUEUE/done/`.
8. Reply to Jean in at most 5 lines: id, status, what changed, the one next action.
