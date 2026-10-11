---
description: Create the worktree for a handoff (branch from origin/main, .env, uv sync) and print how to start it
argument-hint: "<handoff id, e.g. h003>"
---
Run from the main checkout. `QUEUE` = `<main checkout>/.handoffs`.

1. Read `$QUEUE/$ARGUMENTS-*.md`; take `branch:`. Missing file or branch: say so and stop.
2. If `docs/`, `.claude/` or `AGENTS.md` have uncommitted changes in the main checkout: stop and tell Jean to run
   `/sync-docs` first (the handoff's spec must be on main).
3. `git fetch origin`. Path: `../maf-labs-$ARGUMENTS`. If the branch exists, `git worktree add <path> <branch>`;
   else `git worktree add <path> -b <branch> origin/main`.
4. Copy `.env` from the main checkout. In the worktree: `uv sync --all-packages`, `uv run mafx validate`.
5. Reply with exactly the next command:
   `cd ../maf-labs-$ARGUMENTS && claude "/handoff $ARGUMENTS"`
