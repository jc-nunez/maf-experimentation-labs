"""repo-agent MCP server (stdio) for the Claude desktop app, Claude Code and other MCP clients.

Tools:
- ``create_workspace``, ``start_worktree``, ``finish_worktree`` [write]: deterministic code, approved with the
  client's standard tool approval.
- ``workspace_status`` [read]: deterministic code; works without a model.
- ``ask_repo_agent`` [read]: one question to the ``reader`` agent on the host's provider (local Qwen). It only has
  read tools, so no write is reachable from a question.

stdout carries the MCP protocol; everything else goes to stderr. Console script: ``repo-agent-mcp``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from maf_labs_host import create_runner, find_workspace, load_project
from maf_labs_host.events import collect
from maf_labs_host.workspace import load_env
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from repo_agent import workspace, worktree
from repo_agent.guards import Allowlist

PROJECT_DIR = Path(__file__).resolve().parents[3]

INSTRUCTIONS = """\
repo-agent manages the user's workspaces under ~/workspaces/<project>/ (main checkouts, worktrees, handoff queue).
Use workspace_status for status, ask_repo_agent for questions, and create_workspace only when the user wants a new
workspace. start_worktree / finish_worktree start and finish a handoff's worktree (worktrees/<handoff id>); call
them only when the user asks for that handoff. Show tool results exactly as returned.
"""

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True)
START = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True)
FINISH = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True)


def build_server(
    *, repos: dict[str, list[dict[str, Any]]] | None = None, allowlist: Allowlist | None = None
) -> MCPServer:
    """The server. ``repos`` and ``allowlist`` override the defaults (tests clone a local bare origin)."""
    server = MCPServer("repo-agent", instructions=INSTRUCTIONS)
    known_repos = repos if repos is not None else workspace.DEFAULT_REPOS

    @server.tool(
        description=(
            "Create the workspace ~/workspaces/<project>/: clone its repos on their default branch, an empty "
            "worktrees/ folder and .repo-agent/ (config and action log). Idempotent: when everything exists it "
            "changes nothing and says so. Known projects: " + ", ".join(known_repos) + "."
        ),
        annotations=WRITE,
    )
    def create_workspace(project: str = "mafx") -> str:
        if project not in known_repos:
            return f"unknown project '{project}' (known: {', '.join(known_repos)})"
        try:
            result = workspace.create_workspace(project, known_repos[project], caller="mcp", allowlist=allowlist)
        except (PermissionError, workspace.WorkspaceError) as e:
            return f"refused: {e}"
        if result["status"] == "unchanged":
            return f"{result['workspace']}: {result['message']}"
        return f"{result['workspace']}: {result['status']}\n" + "\n".join(f"- {c}" for c in result["changes"])

    @server.tool(
        description=(
            "Start a handoff: create ~/workspaces/<project>/worktrees/<handoff_id> on the handoff's branch (new from "
            "origin/main, or the existing branch), copy .env, run uv sync. Only for a handoff with status ready; "
            "refuses when the main checkout is dirty or the worktree exists. Returns what changed and the command "
            "that starts the handoff in Claude Code."
        ),
        annotations=START,
    )
    def start_worktree(handoff_id: str, project: str = "mafx") -> str:
        try:
            return worktree.format_result(
                worktree.start_worktree(handoff_id, project, caller="mcp", allowlist=allowlist)
            )
        except (PermissionError, worktree.WorktreeError) as e:
            return worktree.format_error(e)

    @server.tool(
        description=(
            "Finish a handoff: remove worktrees/<handoff_id> when it is clean. Branch merged into origin/main: delete "
            "it (git branch -d) and move the handoff to .handoffs/done/. Not merged but fully pushed: keep the "
            "branch. Anything else: refuse and change nothing. Never forces."
        ),
        annotations=FINISH,
    )
    def finish_worktree(handoff_id: str, project: str = "mafx") -> str:
        try:
            return worktree.format_result(
                worktree.finish_worktree(handoff_id, project, caller="mcp", allowlist=allowlist)
            )
        except (PermissionError, worktree.WorktreeError) as e:
            return worktree.format_error(e)

    @server.tool(
        description=(
            "Read-only status table of a workspace: repos (branch, clean, behind/ahead as of the last fetch), "
            "worktrees, handoff queue and open PRs. Show it exactly as returned."
        ),
        annotations=READ,
    )
    def workspace_status(project: str = "mafx") -> str:
        try:
            return workspace.format_status(workspace.workspace_status(project))
        except PermissionError as e:
            return f"refused: {e}"

    @server.tool(
        description=(
            "Ask repo-agent (local model) a question about the workspaces, e.g. 'status' or 'what is in flight?'. "
            "It only reads; it never changes anything. One fresh session per call."
        ),
        annotations=READ,
    )
    async def ask_repo_agent(message: str) -> str:
        return await ask(message)

    return server


async def ask(message: str) -> str:
    """Run one turn of the read-only ``reader`` agent on the host's provider and return its answer."""
    project = load_project(PROJECT_DIR)
    load_env(find_workspace(PROJECT_DIR), PROJECT_DIR)
    runner = create_runner(project, "reader")  # read tools only: a question can never reach a write
    await runner.start()
    try:
        events = await collect(runner.turn(message))
    finally:
        await runner.close()
    done = events[-1] if events else {}
    if not done.get("ok"):
        return f"repo-agent failed: {done.get('error') or 'no answer'}"
    return done.get("text") or "(no answer)"


def main() -> None:
    build_server().run("stdio")


if __name__ == "__main__":
    main()
