"""start_worktree / finish_worktree as agent tools. Both are writes: the host asks the user before every call."""

from __future__ import annotations

from typing import Annotated

from agent_framework import tool
from pydantic import Field

from repo_agent import worktree

HandoffId = Annotated[str, Field(description="Handoff id from the queue, e.g. h007")]
Project = Annotated[str, Field(description="Workspace (project) name, e.g. mafx")]


@tool(
    name="start_worktree",
    description=(
        "Create the worktree ~/workspaces/<project>/worktrees/<handoff_id> for a handoff whose status is ready: "
        "its branch from origin/main (or the existing branch), .env copied, uv sync. Refuses when the handoff is "
        "missing or not ready, the main checkout is dirty, or the worktree exists. Returns what changed and the "
        "command that starts the handoff."
    ),
    approval_mode="always_require",
)
def start_worktree(handoff_id: HandoffId, project: Project = "mafx") -> str:
    try:
        return worktree.format_result(worktree.start_worktree(handoff_id, project, caller="agent"))
    except (PermissionError, worktree.WorktreeError) as e:
        return worktree.format_error(e)


@tool(
    name="finish_worktree",
    description=(
        "Remove the worktree of a handoff when it is clean. Merged into origin/main: also delete the branch (-d) "
        "and move the handoff to .handoffs/done/. Not merged but fully pushed: keep the branch. Otherwise refuse. "
        "Never forces anything."
    ),
    approval_mode="always_require",
)
def finish_worktree(handoff_id: HandoffId, project: Project = "mafx") -> str:
    try:
        return worktree.format_result(worktree.finish_worktree(handoff_id, project, caller="agent"))
    except (PermissionError, worktree.WorktreeError) as e:
        return worktree.format_error(e)
