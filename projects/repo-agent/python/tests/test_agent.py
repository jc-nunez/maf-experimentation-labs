"""workspace_status tool, and the agent showing the same status on the mock provider."""

from pathlib import Path

from maf_labs_host import create_runner, load_project
from maf_labs_host.events import collect
from repo_agent.tools.workspace_status import workspace_status
from repo_agent.workspace import create_workspace, format_status
from repo_agent.workspace import workspace_status as read_status

PROJECT = load_project(Path(__file__).resolve().parents[2])


async def test_tool_workspace_status(root, repos, file_allowlist):
    create_workspace("mafx", repos, allowlist=file_allowlist)
    result = await workspace_status.invoke(arguments={"project": "mafx"}, skip_parsing=True)
    assert result["table"] == format_status(read_status("mafx"))
    assert result["status"]["repos"][0]["name"] == "labs"


async def test_agent_shows_status_on_mock(root, repos, file_allowlist):
    create_workspace("mafx", repos, allowlist=file_allowlist)
    runner = create_runner(PROJECT, "agent", provider="mock")
    await runner.start()
    events = await collect(runner.turn('call:workspace_status {"project": "mafx"}'))
    await runner.close()
    results = [e for e in events if e["type"] == "tool_result"]
    assert results and results[0]["result"]["table"] == format_status(read_status("mafx"))
    assert events[-1]["ok"]


async def test_agent_loads_skill_without_approval():
    runner = create_runner(PROJECT, "agent", provider="mock")
    await runner.start()
    events = await collect(runner.turn('call:load_skill {"skill_name": "workspace-status"}'))
    await runner.close()
    results = [e for e in events if e["type"] == "tool_result"]
    assert results and "# Workspace status" in results[0]["result"]
    assert not any(e["type"] == "approval_request" for e in events)
