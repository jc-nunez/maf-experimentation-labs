"""workspace_status: read-only status of a workspace, as data plus the rendered table."""

from __future__ import annotations

from typing import Annotated, Any

from agent_framework import tool
from pydantic import Field

from repo_agent import workspace


@tool(
    name="workspace_status",
    description=(
        "Read-only status of a workspace under ~/workspaces: each repo's branch, clean or not, behind/ahead (as of "
        "the last fetch) and last commit; worktrees; the handoff queue; open pull requests. Returns `table` (show it "
        "as is) and `status` (the same as data). Never changes anything."
    ),
    approval_mode="never_require",
)
def workspace_status(
    project: Annotated[str, Field(description="Workspace (project) name, e.g. mafx")] = "mafx",
) -> dict[str, Any]:
    status = workspace.workspace_status(project)
    return {"table": workspace.format_status(status), "status": status}
