---
id: 002
status: active
time_box: 2 weeks of evenings (slice 1 within 2 sessions)
started: 2026-10-11
---
# Bet 002: Repo agent

## Problem
Jean has repositories everywhere, on several machines. When interest fades they go stale, take disk space, and
nobody knows their state. Every active repo also repeats the same chores (sync docs, worktrees, branch cleanup,
PR and queue checks).

## So that
One assistant knows every repo, its state and where it lives, keeps active ones in sync, proposes cleanup for stale
ones, and is reachable from Cowork, Claude Code, Codex or any agentic CLI. Jean spends his time designing.

## The demo (bet is done when)
From any tool (Cowork, Claude Code, Codex) or `mafx run repo-agent/agent`, I ask "status", "which repos are stale?",
"sync docs", "start hNNN", "finish hNNN" and get answers or actions; every write asks for my approval.

## Constraints
- Role boundaries in `docs/process/roles.md`: never code, merge, force-push or rewrite history.
- Every git write is a tool with `approval_mode: always_require`.
- Runs on local Qwen through SGLang. Machines: MacBook Pro (macOS), Windows PC, DGX Spark (Linux): Python subprocess,
  no shell-specific syntax.
- Tools ship as a local MCP server (stdio) so Cowork (through the desktop app), Claude Code, Codex and the mafx agent
  share one implementation.
- Inventory scans the whole home folder, skipping system and cache folders (Library, AppData, node_modules, .venv, caches).
- Cross-machine registry: a private GitHub repo, one small JSON file per machine (slice 4).

## Not doing
- Starting Claude Code sessions; merging PRs; editing files outside `docs/` and `.handoffs/` state fields.

## Slices (v1, approved 2026-10-11)
| # | Slice | Demo | Depends on | Status |
|---|---|---|---|---|
| 1 | Create `~/workspaces/mafx/` + read-only status (mafx + MCP) | Cowork creates the workspace (approved) and shows status; `mafx run repo-agent/agent -p "status"` shows the same | none | ✓ done 2026-10-12 ([s01.md](s01.md)) |
| 2 | Worktree start / finish | "start h00N" → approve → worktree ready; "finish" after merge | 1 | |
| 3 | Sync main | "sync" → approve → main pulled, merged branches and prunable worktrees cleaned | 1 | |
| 4 | Push + PR | Builder commits; repo-agent pushes and opens the PR; Builder rules updated | 2 | |

Requirements: [requirements.md](requirements.md) · Architecture: [architecture.md](architecture.md)

## Demo log
| Date | Slice | What Jean saw | Decision |
|---|---|---|---|
| 2026-10-12 | 1 | Cowork created `~/workspaces/mafx/` (approved) and read status; idempotent re-run; `mafx run repo-agent/agent -p "status"` on Qwen gave the same table (15 s, skill loaded, 1 read tool); MCP server moved to the workspace clone; planning worktree + handoff queue moved into the workspace | next: slice 2. Polish: P1 strip leading blank lines (host), P2 truncate long PR titles |

## Outcome
<open>
