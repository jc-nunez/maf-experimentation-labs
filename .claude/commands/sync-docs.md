---
description: Commit and push the docs and handoff tooling Cowork changed in the main checkout
---
Run only in the main checkout on `main` (stop and say so otherwise).

1. `git pull --ff-only`.
2. List uncommitted changes under `docs/`, `.claude/`, `AGENTS.md`, `.github/`. Nothing: say so and stop.
   Any other path changed: list it and stop (not Cowork's).
3. Group them into Conventional Commits (scope from the path: `docs(mail)` for `docs/bets/001-*`, `docs` for the rest,
   `chore` for `.claude/` and `.github/`). Show the plan in one table, then commit and push.
4. Reply in at most 3 lines: commits and pushed SHA.
