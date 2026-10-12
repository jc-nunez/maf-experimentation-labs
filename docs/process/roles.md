# Roles

| Role | Who | Owns | Never |
|---|---|---|---|
| Owner | Jean | decisions, approvals, PR review and merge, demo | |
| Tech Lead + Architect (planner) | Claude (Cowork) | shape, slice, design, specs, handoffs; needs to know what exists in the workspace | git, code |
| Builder | Claude Code | implements a handoff in its worktree and commits its work | push, PRs, merge, work outside `touches:` |
| Repo agent | MAF harness agent, local Qwen (`mafx run repo-agent/agent`), reachable over MCP | the only role for PRs, clones, branch sync, worktrees, inventory, references; serves the Tech Lead | code, merge, force-push, history rewrite |
| Mail assistant | MAF harness agent, local Qwen (`mafx run mail/assistant`) | Jean's mailboxes | |

```
 Planner          Repo agent                    Builder             Owner        Repo agent
 handoff hNNN ──► sync docs → main         ──►  /handoff hNNN  ──►  review + ──► remove worktree
                  create worktree (env, sync)   commits, PR         merge        delete branch, pull
                  queue: in-progress                                             queue: done
```
Until the repo agent has each capability, Claude Code commands cover it: `/sync-docs`, `/wt-new`, `/wt-done`.

## Floors (which conversation works at which altitude)
| Floor | Question | Where | Artifacts |
|---|---|---|---|
| 3 Why / what | which problem, which bet, what is the demo | Cowork with Jean | `NOW.md`, `bet.md`, inbox |
| 2 How (design) | slice, design, interfaces, decisions; Jean approves | Cowork with Jean | `sNN.md`, handoffs |
| 1 Build / operate | code, tests, git, worktrees, repos on disk | Claude Code, repo agent | branches, PRs, reports |

A conversation declares its floor. A topic from another floor becomes one inbox line, then back to the floor.
