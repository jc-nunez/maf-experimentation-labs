# repo-agent

Repo agent ([bet 002](../../docs/bets/002-repo-agent/bet.md), slice 1). Creates the workspace
`~/workspaces/mafx/` and reports its status: repos, worktrees, handoff queue, open PRs. The only write is
`create_workspace`; everything else reads.

| Component | Runtime | What it does |
|---|---|---|
| `agent` | python harness agent | skill `workspace-status`; read tools only |
| `workspace-status` | python tool | status of `~/workspaces/<project>/` as data plus the rendered table |
| `repo-agent-mcp` | console script | stdio MCP server: `create_workspace` [write], `workspace_status`, `ask_repo_agent` [read] |

```
 Claude desktop ──stdio──► repo_agent/mcp_server.py ──┐        mafx run repo-agent/agent
                                                      ▼                 │
                         workspace.py (create · status) ◄── agents/agent.py + skills/workspace-status
                         guards.py (PathGuard · Allowlist · ActionLog) · git.py (runner, no shell)
```

## Workspace
```
~/workspaces/mafx/                     # REPO_AGENT_ROOT overrides ~/workspaces
  maf-experimentation-labs/            # clone on main
  worktrees/
  .repo-agent/config.yaml              # project, repos [{name, url, default_branch}]
  .repo-agent/actions.jsonl            # one line per write: time, caller, tool, argv, result
```
Guards (in code, not prompts): every path must be inside `~/workspaces/<project>/`; a command runs only if its argv
matches the slice 1 allowlist exactly (`git clone -- <https url> <path>`, `git status --porcelain=v2 --branch`,
`git worktree list --porcelain`, `git log -1 --format=…`, `gh pr list --state open --json …`).

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
3. Quit and reopen the desktop app. Settings → Developer shows `repo-agent` running with 3 tools.

`ask_repo_agent` uses the provider from the repo's `.env` (local Qwen via SGLang). `create_workspace` and
`workspace_status` need no model.

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

Check the log: `cat ~/workspaces/mafx/.repo-agent/actions.jsonl` (one entry after step 1).

## Tests
```bash
uv run pytest projects/repo-agent    # offline: temp dirs, bare origin, mock provider, MCP server in-process
```
