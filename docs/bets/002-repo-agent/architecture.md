---
bet: 002
status: approved 2026-10-11
requirements: requirements.md (v1)
---
# repo-agent architecture (draft)

## Context
```
 ┌──────────── MacBook Pro (macOS, native) ───────────────────────────────────────────────────┐
 │                                                                                            │
 │  Jean ── terminal ── mafx run repo/agent ──┐                                                │
 │                                            │                                                │
 │  Cowork ── Claude desktop app ── MCP ──────┤  (stdio, launched by the desktop app)          │
 │  (Tech Lead)   ask_repo_agent(message)     │                                                │
 │                                            ▼                                                │
 │                      ┌──────────────── repo-agent ─────────────────┐     ┌──────────────┐  │
 │                      │ Entry: mafx host · MCP server                │     │ Qwen (SGLang)│  │
 │                      │ Core:  harness agent (MAF) ◄────────────────────────┤ on DGX Spark │  │
 │                      │ Skills: status · workspace · sync · worktree │     └──────────────┘  │
 │                      │         · push-and-pr                         │                       │
 │                      │ Tools:  read tools · write tools (approval)   │                       │
 │                      │ Guards: path guard · command allowlist ·      │                       │
 │                      │         preconditions · action log            │                       │
 │                      └──────────────────────┬───────────────────────┘                       │
 │                                             │ git · gh (your credentials)                    │
 │                                             ▼                                                │
 │                      ~/workspaces/mafx/                                                       │
 │                         .repo-agent/  config · action log · memory                            │
 │                         maf-experimentation-labs/   (main, synced)                            │
 │                         worktrees/<branch>/         (Builder works here)                      │
 └─────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               │ push · PR
                                               ▼
                                            GitHub ── Jean reviews + merges
```

## Components
| # | Component | Responsibility | Built on |
|---|---|---|---|
| C1 | mafx entry | interactive and `-p` sessions for Jean; relays approvals | existing mafx host |
| C2 | MCP server | runs natively on macOS, launched by the Claude desktop app. `ask_repo_agent(message)` for questions and plans (no writes); one MCP tool per write workflow (`create_workspace`, `sync_main`, `start_worktree`, `finish_worktree`, `push_and_pr`), each approved through Cowork's standard tool approval | Python MCP SDK, stdio |
| C3 | Agent core | charter as instructions; plans and runs skills; file memory in `.repo-agent/memory/` | `create_harness_agent` (MAF), local Qwen |
| C4 | Skills | one SKILL.md per workflow, each with a checklist: `workspace-status`, `create-workspace`, `sync-main`, `start-worktree`, `finish-worktree`, `push-and-pr` | MAF skills (progressive disclosure) |
| C5 | Read tools | `workspace_status`, `repo_status`, `worktrees`, `pr_status`, `handoff_queue` | function tools |
| C6 | Write tools | `workspace_init`, `clone_repo`, `pull_main`, `worktree_add`, `worktree_remove`, `worktree_prune`, `branch_delete`, `push_branch`, `pr_create`; all `approval_mode: always_require` | function tools |
| C7 | Guards | path guard (only `~/workspaces/<project>/`), command allowlist (argv patterns, no force), preconditions in code (N2: nothing unpushed or uncommitted is removed) | shared module used by every tool |
| C8 | State | `.repo-agent/config.yaml` (root, repos, allowlist), `action-log.jsonl` (every command, who asked, result) | files in the workspace |

## Flow: "start h005"
```
 caller ─► C1/C2 ─► C3 picks skill start-worktree
                     checklist: handoff h005 ready? · branch name · main clean and synced?
                     C5 reads ─► C7 guards ─► C6 worktree_add  ── approval ──► Jean
                     ─► C8 action log ─► reply: path + "claude \"/handoff h005\""
```

## Traceability (v1 requirements)
| Req | Met by | Status |
|---|---|---|
| R1 status of each repo | C5 `repo_status`, `workspace_status` · skill `workspace-status` | ✓ |
| R4 sync main, clean merged branches and prunable worktrees | C6 `pull_main`, `branch_delete`, `worktree_prune` · skill `sync-main` | ✓ |
| R5 worktree lifecycle | C6 `worktree_add`, `worktree_remove` · skills `start-worktree`, `finish-worktree` | ✓ |
| R6 PR and handoff status | C5 `pr_status`, `handoff_queue` | ✓ |
| R7 Cowork over local MCP | C2 | ✓ |
| R8 Qwen session | C1 + C3 | ✓ |
| R11 workspace layout | C8 + `workspace_init` | ✓ |
| R12 access only workspace paths | C7 path guard | ✓ |
| R24 only role that pushes and opens PRs | C6 `push_branch`, `pr_create` · skill `push-and-pr` | ⚠ also needs the Builder rules changed (no push, no PR) when slice "push-and-pr" ships |
| R25 create a workspace | C6 `workspace_init`, `clone_repo` · skill `create-workspace` | ✓ |
| N1 approval, never merge or force | C6 approval mode · Cowork tool approval · C7 allowlist | ✓ |
| N2 never remove unpushed or uncommitted work | C7 preconditions in code, not only in skill checklists | ✓ |

Resilience: the MCP write tools are deterministic code (skills' checklists implemented as preconditions), so they work
even when Qwen is unreachable; only `ask_repo_agent` and mafx sessions need the model.

## Open design decisions
| # | Question | Options |
|---|---|---|
| D1 | ✓ Writes from Cowork are approved with the standard MCP tool approval (Jean, 2026-10-11). Consequence: each write workflow is its own MCP tool; `ask_repo_agent` never writes | decided |
| D2 | MCP session model: one agent session per `conversation_id`, or one per call? | per conversation · per call |
| D3 | ✓ Code lives in `projects/repo-agent/` in maf-experimentation-labs | decided |
