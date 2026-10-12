"""workspace_status tool, and the agent showing the same status on the mock provider."""

from pathlib import Path

from maf_labs_host import create_runner, load_project
from maf_labs_host.events import collect
from repo_agent.guards import ActionLog
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


async def test_agent_asks_approval_before_starting_a_worktree(root, repos, file_allowlist, monkeypatch):
    from repo_agent import worktree

    create_workspace("mafx", repos, allowlist=file_allowlist)
    ws = root.resolve() / "mafx"
    (ws / "labs" / ".git" / "info" / "exclude").write_text(".handoffs/\n")
    (ws / "labs" / ".handoffs").mkdir()
    (ws / "labs" / ".handoffs" / "h900-demo.md").write_text("---\nstatus: ready\nbranch: test/h900-demo\n---\n")
    start = worktree.start_worktree
    monkeypatch.setattr(worktree, "start_worktree", lambda *a, **k: start(*a, **{**k, "allowlist": file_allowlist}))
    runner = create_runner(PROJECT, "agent", provider="mock")
    await runner.start()

    asked = await collect(runner.turn('call:start_worktree {"handoff_id": "h900"}'))
    requests = [e for e in asked if e["type"] == "approval_request"]
    assert [r["name"] for r in requests] == ["start_worktree"]
    assert not (ws / "worktrees" / "h900").exists()  # nothing runs before the user approves

    done = await collect(runner.approve({requests[0]["request_id"]: "approve"}))
    await runner.close()
    results = [e for e in done if e["type"] == "tool_result"]
    assert results and "h900: started" in results[0]["result"]
    assert (ws / "worktrees" / "h900").is_dir()
    assert ActionLog(ws / ".repo-agent" / "actions.jsonl").entries()[-1]["caller"] == "agent"


async def test_agent_write_tools_always_require_approval():
    runner = create_runner(PROJECT, "agent", provider="mock")
    await runner.start()
    tools = {t.name: t for t in runner.tools}
    await runner.close()
    assert tools["start_worktree"].approval_mode == "always_require"
    assert tools["finish_worktree"].approval_mode == "always_require"
    assert tools["workspace_status"].approval_mode == "never_require"
