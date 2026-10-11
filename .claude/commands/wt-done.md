---
description: After a handoff's PR is merged, remove its worktree and branch and update main
argument-hint: "<handoff id, e.g. h003>"
---
Run from the main checkout.

1. Find the worktree `../maf-labs-$ARGUMENTS` and its branch (from `git worktree list` or the handoff file in
   `.handoffs/` or `.handoffs/done/`).
2. `git fetch origin`. Check the PR for the branch is merged (`gh pr view <branch> --json state,mergedAt`, or the
   branch is an ancestor of `origin/main`). Not merged: say so and stop.
3. Worktree has uncommitted changes or untracked (non-ignored) files: list them and stop.
4. `git worktree remove ../maf-labs-$ARGUMENTS`; `git branch -d <branch>`; `git switch main && git pull --ff-only`.
5. Make sure the handoff file is in `.handoffs/done/`.
6. Reply in at most 3 lines: removed path, deleted branch, main SHA.
