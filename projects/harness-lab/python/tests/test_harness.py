"""Harness agents: tool calling on the mock (python + .NET), and the plan/execute flow live."""

import os
import shutil
from pathlib import Path

import pytest
from maf_labs_host import create_runner, find_workspace, load_project
from maf_labs_host.events import collect
from maf_labs_host.workspace import load_env

ROOT = Path(__file__).resolve().parents[2]
PROJECT = load_project(ROOT)


async def test_claw_calls_stock_tool_on_mock():
    runner = create_runner(PROJECT, "claw", provider="mock")
    await runner.start()
    events = await collect(runner.turn('call:get_stock_price {"symbol": "NVDA"}'))
    await runner.close()
    results = [e for e in events if e["type"] == "tool_result"]
    assert results and results[0]["result"]["price"] == 134.81
    assert events[-1]["ok"]


@pytest.mark.skipif(shutil.which("dotnet") is None, reason=".NET SDK not installed")
async def test_claw_dotnet_calls_stock_tool_on_mock():
    from mafx import targets

    tgt = targets.resolve(find_workspace(ROOT), "harness-lab/claw-dotnet")
    runner = targets.make_runner(tgt, provider="mock", model=None, record=False, mode="once")
    await runner.start()
    try:
        events = await collect(runner.turn('call:get_stock_price {"symbol": "NVDA"}'))
    finally:
        await runner.close()
    results = [e for e in events if e["type"] == "tool_result"]
    assert results and results[0]["result"]["price"] == 134.81
    assert events[-1]["ok"]


load_env(find_workspace(ROOT), ROOT)


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("SGLANG_BASE_URL"), reason="no endpoint configured (.env)")
async def test_claw_plans_executes_and_remembers():
    runner = create_runner(PROJECT, "claw")
    await runner.start()
    first = await collect(
        runner.turn(
            "My watchlist is MSFT and NVDA. Make a todo per ticker to get its price and note it in watchlist.md, "
            "then execute the plan without asking me."
        )
    )
    second = await collect(runner.turn("Which ticker in my watchlist has the lower price?"))
    await runner.close()
    names = [e["name"] for e in first if e["type"] == "tool_call"]
    assert first[-1]["ok"] and second[-1]["ok"]
    assert "todos_add" in names and "get_stock_price" in names and "file_memory_write" in names
    assert "NVDA" in second[-1]["text"]
