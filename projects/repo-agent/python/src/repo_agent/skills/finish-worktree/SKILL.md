---
name: finish-worktree
description: Finish a handoff whose PR is merged or pushed, for requests such as "finish h007" or "clean up the worktree of h007".
---
# Finish worktree

## Checklist
1. Get the handoff id (`h` plus digits) from the request. None given: call `workspace_status`, list the worktrees
   and ask which one. Stop.
2. Call `finish_worktree` once with that id (project: the one the user names; otherwise `mafx`). The user approves it.
3. Reply with the tool result as returned, inside a code block.

## Rules
- A reply that starts with `refused:` changed nothing: show the reason and what would fix it (commit, push or merge
  first), in one line. Do not retry.
- A kept branch is expected when the work is pushed but not merged; say so.
- Never suggest `--force` or `git branch -D`.
