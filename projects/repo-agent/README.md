# repo-agent

Creates the workspace `~/workspaces/mafx/`, reports its status (repos, worktrees, handoff queue, open PRs) and
starts / finishes a handoff's worktree. Writes: `create_workspace`, `start_worktree`, `finish_worktree`; each one
asks for approval (MCP client or mafx). Everything else reads.

| Component | Runtime | What it does |
|---|---|---|
| `agent` | python harness agent | skills `workspace-status`, `start-worktree`, `finish-worktree`; writes ask first |
| `reader` | python harness agent | skill `workspace-status`, read tools only; behind `ask_repo_agent` |
| `workspace-status` | python tool | status of `~/workspaces/<project>/` as data plus the rendered table |
| `start-worktree`, `finish-worktree` | python tools | `approval_mode: always_require` |
| `repo-agent-mcp` | console script | stdio MCP server: `create_workspace`, `start_worktree`, `finish_worktree` [write]; `workspace_status`, `ask_repo_agent` [read] |

```
 Claude desktop ──stdio──► repo_agent/mcp_server.py ──┐        mafx run repo-agent/agent
                                                      ▼                 │
        workspace.py (create · status) · worktree.py (start · finish) ◄── agents/agent.py + skills/
                         guards.py (PathGuard · Allowlist · ActionLog) · git.py (runner, no shell)
```

## Workspace
```
~/workspaces/mafx/                     # REPO_AGENT_ROOT overrides ~/workspaces
  maf-experimentation-labs/            # clone on main
  worktrees/<handoff id>/              # one per started handoff, on the handoff's branch
  .repo-agent/config.yaml              # project, repos [{name, url, default_branch}]
  .repo-agent/actions.jsonl            # one line per write: time, caller, tool, argv, result
```
Guards (in code, not prompts): every path must be inside `~/workspaces/<project>/`; a command runs only if its argv
matches the default allowlist exactly (`guards.py: DEFAULT_PATTERNS`: clone, status, fetch, worktree add / list /
remove, `branch -d`, merge-base, rev-parse, rev-list, `gh pr list`, `uv sync --all-packages`). No force form is on
it (`worktree remove --force`, `branch -D`). File operations never follow a symbolic link.

## Worktree start / finish
| Tool | Refuses when | Does |
|---|---|---|
| `start_worktree(id)` | handoff missing or not `ready`, main checkout dirty, `worktrees/<id>` exists | fetch; `worktree add` (new branch from `origin/main`, or the existing one); copy `.env`; `uv sync`; replies `cd … && claude "/handoff <id>"` |
| `finish_worktree(id)` | worktree dirty; branch neither merged into `origin/main` nor fully pushed | fetch; `worktree remove`; merged: `branch -d` and handoff → `.handoffs/done/`; pushed only: branch kept |

`uv sync` builds the branch's packages, so it runs that branch's build code: start only handoffs you trust.

## Register in the Claude desktop app (once)

1. Open `~/Library/Application Support/Claude/claude_desktop_config.json` (Settings → Developer → Edit Config).
2. Add under `mcpServers` (use your checkout path; the desktop app needs the absolute path to `uv`):
   ```json
   "repo-agent": {
     "command": "/opt/homebrew/bin/uv",
     "args": ["--directory", "/Users/jnunez/Work/Trossitec/repos/labs/maf-experimentation-labs",
              "run", "--package", "repo-agent", "repo-agent-mcp"]
   }
   ```
3. Quit and reopen the desktop app. Settings → Developer shows `repo-agent` running with 5 tools.

`ask_repo_agent` uses the provider from the repo's `.env` (local Qwen via SGLang). The other four tools need no
model.

## Demo

1. Cowork: "create the mafx workspace" → calls `create_workspace` → approve → `~/workspaces/mafx/` exists.
   Ask again: it answers "workspace already exists; nothing changed".
2. Cowork: "show workspace status" → calls `workspace_status("mafx")`:
   ```
    WORKSPACE  ~/workspaces/mafx
    REPOS      maf-experimentation-labs  main  ✓ clean  behind 0 (as of last fetch)
    WORKTREES  none
    HANDOFFS   none
    PRS        none open
   ```
3. Terminal: `mafx run repo-agent/agent -p "status"` shows the same table.
4. Cowork: `ask_repo_agent("what is in flight?")` answers from the status (read tools only).
5. Put a test handoff `h900` (`status: ready`, `branch: test/h900-demo`) in `.handoffs/`. Cowork:
   `start_worktree("h900")` → approve → `~/workspaces/mafx/worktrees/h900/` on `test/h900-demo`; the reply ends with
   `cd … && claude "/handoff h900"`. `start_worktree("h003")` (a draft) → `refused: h003 is draft, not ready`.
6. Cowork: `finish_worktree("h900")` → approve → worktree removed, branch deleted (no commits, so merged), `h900`
   moved to `.handoffs/done/`.
7. Terminal: `mafx run repo-agent/agent`, "start h900" → mafx asks for approval → same result as step 5.

Check the log: `cat ~/workspaces/mafx/.repo-agent/actions.jsonl` (one entry per write).

## Tests
```bash
uv run pytest projects/repo-agent    # offline: temp dirs, bare origin, mock provider, MCP server in-process
```
