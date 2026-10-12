"""MCP server in-process: the three tools, and ask_repo_agent reaching only read tools."""

import pytest
from maf_labs_host import create_runner
from mcp import Client
from repo_agent.mcp_server import PROJECT_DIR, build_server, load_project
from repo_agent.workspace import format_status, workspace_status


@pytest.fixture
def server(repos, file_allowlist, root, monkeypatch):
    monkeypatch.setenv("MAF_PROVIDER", "mock")
    return build_server(repos={"mafx": repos}, allowlist=file_allowlist)


def text(result) -> str:
    return "".join(c.text for c in result.content if c.type == "text")


async def test_lists_five_tools_with_read_and_write_hints(server):
    async with Client(server) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == {"create_workspace", "start_worktree", "finish_worktree", "workspace_status", "ask_repo_agent"}
    for name in ("create_workspace", "start_worktree", "finish_worktree"):
        assert tools[name].annotations.read_only_hint is False
    assert tools["finish_worktree"].annotations.destructive_hint is True
    assert tools["workspace_status"].annotations.read_only_hint is True
    assert tools["ask_repo_agent"].annotations.read_only_hint is True


async def test_create_then_status(server, root):
    async with Client(server) as client:
        created = text(await client.call_tool("create_workspace", {"project": "mafx"}))
        again = text(await client.call_tool("create_workspace", {"project": "mafx"}))
        status = text(await client.call_tool("workspace_status", {"project": "mafx"}))
    assert "created" in created and "cloned labs" in created
    assert "nothing changed" in again
    assert status == format_status(workspace_status("mafx"))
    assert " REPOS      labs  main  ✓ clean  behind 0 (as of last fetch)" in status


async def test_create_refuses_unknown_project(server, root):
    async with Client(server) as client:
        reply = text(await client.call_tool("create_workspace", {"project": "other"}))
    assert reply.startswith("unknown project") and not (root / "other").exists()


async def test_ask_repo_agent_answers_from_read_tools(server):
    async with Client(server) as client:
        await client.call_tool("create_workspace", {"project": "mafx"})
        reply = text(await client.call_tool("ask_repo_agent", {"message": 'call:workspace_status {"project": "mafx"}'}))
    assert '"name": "labs"' in reply and '"clean": true' in reply  # the mock echoes the tool result as JSON


async def test_ask_repo_agent_cannot_reach_a_write(server, root):
    async with Client(server) as client:
        await client.call_tool("ask_repo_agent", {"message": 'call:create_workspace {"project": "mafx"}'})
    assert not (root / "mafx").exists()


async def test_ask_repo_agent_uses_a_reader_with_only_read_tools(monkeypatch):
    monkeypatch.setenv("MAF_PROVIDER", "mock")
    runner = create_runner(load_project(PROJECT_DIR), "reader")
    await runner.start()
    host_tools = {t.name for t in runner.tools}
    own_tools = {getattr(t, "name", "") for t in runner.agent.default_options.get("tools") or []}
    await runner.close()
    assert host_tools == {"workspace_status"}
    assert not own_tools & {"create_workspace", "start_worktree", "finish_worktree"}


async def test_start_and_finish_a_worktree(server, root):
    async with Client(server) as client:
        await client.call_tool("create_workspace", {"project": "mafx"})
        labs = root.resolve() / "mafx" / "labs"
        (labs / ".git" / "info" / "exclude").write_text(".handoffs/\n")
        (labs / ".handoffs").mkdir()
        (labs / ".handoffs" / "h003-mail.md").write_text("---\nstatus: draft\nbranch: bet/001-s02\n---\n")
        (labs / ".handoffs" / "h900-demo.md").write_text("---\nstatus: ready\nbranch: test/h900-demo\n---\n")

        draft = text(await client.call_tool("start_worktree", {"handoff_id": "h003"}))
        started = text(await client.call_tool("start_worktree", {"handoff_id": "h900"}))
        status = text(await client.call_tool("workspace_status", {"project": "mafx"}))
        finished = text(await client.call_tool("finish_worktree", {"handoff_id": "h900"}))

    path = root.resolve() / "mafx" / "worktrees" / "h900"
    assert draft == "refused: h003 is draft, not ready"
    assert started.startswith(f"h900: started ({path})") and started.endswith(f'cd {path} && claude "/handoff h900"')
    assert "test/h900-demo" in status
    assert "deleted branch test/h900-demo" in finished and "moved h900-demo.md to .handoffs/done/" in finished
    assert not path.exists()
