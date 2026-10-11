---
bet: 002
status: approved 2026-10-11   # v1 scope
---
# Bet 002 requirements: repo agent

## Version 1 (Jean, 2026-10-11)
Create a workspace for mafx (`~/workspaces/mafx/`) and an agent that handles it: status, sync, worktrees, push and
PRs for that workspace, used by Cowork through a local MCP server and by Jean through `mafx run`. Everything marked Later waits.

Captured from Jean. No design until this file is `approved`.

## Charter
| Part | Content | Source |
|---|---|---|
| Identity | working name `repo-agent` (final name later) · local agent on Qwen, one per machine, reachable over MCP | Jean |
| Role | owns the repository capability of the platform | Jean |
| Scope in | repos and worktrees inside the project template's paths, and their operations (sync, worktrees, branches, PR and queue status, inventory, cleanup) | Jean |
| Scope out | code, merges, force-push, history rewrite (N1); planning (Planner), building (Builder); moving sessions between tools or machines (Jean does it manually) | roles.md, Jean |
| Communication | controlled channels: direct with Jean, messages from other agents, workflow triggers | Jean |
| Responsibilities | Inventory (R1, R2, R9) · Hygiene and cleanup (R3) · Sync (R4) · Build-cycle support (R5) · Reporting (R6) · Access (R7, R8) | grouped from R1 to R9 |

## Requirements
| ID | Requirement | Priority |
|---|---|---|
| R1 | Knows every repo on each machine: path, remote, branch, last commit, uncommitted and unpushed work, size | Must |
| R2 | Flags stale repos (no commits in 90 days) and the disk space they use | Later |
| R3 | Proposes cleanup (archive or delete) only when everything is pushed; acts only after approval | Later |
| R4 | Keeps active repos in sync: docs to main, pull, merged branches, prunable worktrees | Must |
| R5 | Runs the worktree lifecycle for handoffs (start, finish) | Must |
| R6 | Reports PR and handoff queue status | Must |
| R7 | v1: Cowork (Tech Lead) reaches repo-agent through a local MCP server run by the Claude desktop app; writes use Cowork's standard tool approval | Must |
| R7b | The same MCP server registered in Claude Code, Codex and other MCP-capable CLIs | Later |
| R8 | Interactive session on local Qwen (`mafx run repo/agent`) | Must |
| R9 | One inventory across MacBook Pro, Windows PC and DGX Spark (private GitHub registry) | Later |

## Boundaries
| ID | Rule |
|---|---|
| N1 | Every write needs Jean's approval; never merge, force-push, rewrite history or edit code |
| N2 | Never delete or archive a repo with unpushed or uncommitted work |
| N3 | Flags repos that may hold customer code; never proposes cleaning them without Jean's explicit OK |
| N4 | Repo contents stay on the machine; only summary metadata goes to the registry |

## Jean's additional requirements
| ID | Requirement | Priority |
|---|---|---|
| R10 | Communication is controlled: the agent talks directly to Jean, or receives messages from other agents or workflows; Jean decides which channels are enabled | Later |
| R11 | A project template defines where a project's repos and worktrees live | Must |
| R12 | The agent can access only the repos and worktrees paths defined by the template | Must |
| R13 | One-time migration: find scattered repos (read-only scan), propose where each goes in the workspace, move with approval | Later |
| R14 | Reference repos: read-only, kept for agent context; pulled to stay current; never flagged as stale | Later |
| R15 | Messages from other agents may run pre-approved safe actions alone (e.g. remove a merged, clean worktree); every other write asks Jean | Later |
| R16 | Jean can switch communication channels on or off | Later |
| R17 | Command allowlist: the agent runs only a minimal allowlisted set of commands; anything else is refused | Later |
| R18 | Each workflow is a skill with a checklist the agent verifies before acting (e.g. close worktree) | Later |
| R19 | A worktree still in progress is removed only if its branch exists on the remote with every commit pushed | Later |
| R20 | Jean can ask the agent to add a reference repo (clone with approval) | Later |
| R21 | repo-agent manages reference repos (clone, pull, catalog) but does not use them; the Tech Lead and Architect (today Claude in Cowork, later dedicated agents) discover them (name, path, purpose, commit) and search them for their task | Later |
| R22 | The Tech Lead and Architect can query the whole workspace (repos, worktrees, references, state) at the start of a session | Later |
| R23 | The Tech Lead (Claude in Cowork) reaches repo-agent through mafx/MCP to request work areas, get information, and manage how many sessions run in parallel | Later |
| R24 | repo-agent is the only role that manages PRs, clones, branch sync (push, pull) and worktrees; no other role does | Must |
| R25 | repo-agent creates a new workspace for a project when the Tech Lead requests it (with Jean's approval) | Must |

## Open questions
| # | Question | Raised by |
|---|---|---|
| Q1 | ✓ Workspace layout (Jean): one root path the agent can access; main checkouts synced on `main`; a `worktrees/` subfolder. See "Workspace layout" below | R11 |
| Q2 | ✓ Scattered repos: a one-time migration job (R13); afterwards the agent works only inside the workspace | R12 |
| Q3 | ✓ Safe actions run alone, the rest ask Jean (R15) | R10, N1 |
| Q4 | ✓ Not needed now (R16, Later) | R10 |
| Q5 | ✓ Minimal command allowlist (R17) + workflow checklists in skills (R18, R19) | R15 |
| Q6 | ✓ Read-only, for agent context (R14, R20, R21) | R14 |
| Q8 | ✓ Builder commits its work; repo-agent pushes and opens the PR; Jean reviews and merges | R24 |
| Q9 | ✓ A workspace is the boundary where source control lives for a project (R25) | R23 |
| Q10 | ✓ One root folder per machine: `~/workspaces/<project>/` | R25 |
| Q7 | ✓ A `references/` folder in the workspace | R14 |

## Workspace layout (Jean, 2026-10-11)
A workspace is the boundary where source control lives for one project. All workspaces sit under one root per machine.
The agent can access only workspace paths.
```
~/workspaces/
 <project>/
   .repo-agent/           agent state: config, inventory, action log
   repo-a/                main checkout, on main, kept synced
   repo-b/                main checkout, on main, kept synced
   worktrees/
       feature-x-y-z/     one per branch or handoff; Builder works and commits here
   references/
       agent-framework/   read-only, for the Tech Lead and Architect
```

## Use cases
| # | Scenario |
|---|---|
| U1 | Jean builds MAF agents: the agent-framework repo is cloned as a reference; repo-agent keeps it cloned and current; the Tech Lead and Architect (Claude in Cowork today) discover it (through a skill or tool) and search it when designing capabilities |
