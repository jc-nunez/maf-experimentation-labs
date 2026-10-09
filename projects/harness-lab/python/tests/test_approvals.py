"""Tool approval relay: pending approvals, approve / deny / always, -p policies, python and .NET hosts."""

import shutil
import uuid
from pathlib import Path

import pytest
from maf_labs_host import create_runner, find_workspace, load_project
from maf_labs_host.approvals import drive, policy
from maf_labs_host.events import collect

ROOT = Path(__file__).resolve().parents[2]
PROJECT = load_project(ROOT)
WRITE = 'call:file_access_write {{"file_name": "{name}", "content": "x"}}'


def _name(stem: str) -> str:
    """Unique per run: the analyst's working folder persists between runs."""
    return f"test-{stem}-{uuid.uuid4().hex[:8]}.md"


async def _analyst():
    runner = create_runner(PROJECT, "analyst", provider="mock", workspace_root=find_workspace(ROOT).root)
    await runner.start()
    return runner


async def test_write_waits_for_approval_and_runs_when_approved(tmp_path):
    runner = await _analyst()
    events = await collect(runner.turn(WRITE.format(name=_name("approved"))))
    pending = events[-1]["pending_approvals"]
    assert [p["name"] for p in pending] == ["file_access_write"]
    assert any(e["type"] == "approval_request" for e in events)

    after = await collect(runner.approve({pending[0]["request_id"]: "approve"}))
    assert after[0] == {**after[0], "type": "approval_decision", "decision": "approve"}
    results = [e for e in after if e["type"] == "tool_result"]
    assert "written" in str(results[0]["result"]) and after[-1]["pending_approvals"] == []
    await runner.close()


async def test_missing_decisions_are_denied():
    runner = await _analyst()
    events = await collect(runner.turn(WRITE.format(name=_name("denied"))))
    assert events[-1]["pending_approvals"]
    after = await collect(runner.approve({}))
    assert after[0]["decision"] == "deny"
    assert "rejected" in str([e for e in after if e["type"] == "tool_result"][0]["result"])
    await runner.close()


async def test_always_creates_a_standing_rule_for_the_session():
    runner = await _analyst()
    events = await collect(runner.turn(WRITE.format(name=_name("first"))))
    await collect(runner.approve({events[-1]["pending_approvals"][0]["request_id"]: "always"}))
    second = await collect(runner.turn(WRITE.format(name=_name("second"))))
    assert second[-1]["pending_approvals"] == []
    assert not any(e["type"] == "approval_request" for e in second)
    await runner.close()


async def test_drive_with_policy_allows_only_named_tools():
    runner = await _analyst()
    events = await collect(drive(runner, runner.turn(WRITE.format(name=_name("p"))), policy(allow_tools=["other"])))
    assert [e["decision"] for e in events if e["type"] == "approval_decision"] == ["deny"]
    events = await collect(
        drive(runner, runner.turn(WRITE.format(name=_name("p"))), policy(allow_tools=["file_access_write"]))
    )
    assert [e["decision"] for e in events if e["type"] == "approval_decision"] == ["approve"]
    await runner.close()


@pytest.mark.skipif(shutil.which("dotnet") is None, reason=".NET SDK not installed")
async def test_dotnet_host_relays_approvals():
    from mafx import targets

    tgt = targets.resolve(find_workspace(ROOT), "harness-lab/analyst-dotnet")
    runner = targets.make_runner(tgt, provider="mock", model=None, record=False, mode="once")
    await runner.start()
    try:
        events = await collect(
            runner.turn('call:file_access_write {"fileName": "' + _name("dotnet") + '", "content": "x"}')
        )
        pending = events[-1]["pending_approvals"]
        assert [p["name"] for p in pending] == ["file_access_write"]
        after = await collect(runner.approve({pending[0]["request_id"]: "approve"}))
        assert after[0]["type"] == "approval_decision" and after[0]["decision"] == "approve"
        assert after[-1]["ok"] and after[-1]["pending_approvals"] == []
    finally:
        await runner.close()
