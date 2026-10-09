""".NET hosts on the mock provider, driven exactly as mafx drives them (skipped without the .NET SDK)."""

import shutil
from pathlib import Path

import pytest
from maf_labs_host import find_workspace
from maf_labs_host.events import collect

pytestmark = pytest.mark.skipif(shutil.which("dotnet") is None, reason=".NET SDK not installed")

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("target", ["greeter-dotnet", "greeter-dotnet-file"])
async def test_dotnet_agent_calls_tool(target):
    from mafx import targets

    tgt = targets.resolve(find_workspace(ROOT), f"hello-world/{target}")
    runner = targets.make_runner(tgt, provider="mock", model=None, record=False, mode="once")
    await runner.start()
    try:
        events = await collect(runner.turn('call:get_weather {"city": "Paris"}'))
        second = await collect(runner.turn("again"))
    finally:
        await runner.close()
    calls = [e for e in events if e["type"] == "tool_call"]
    results = [e for e in events if e["type"] == "tool_result"]
    assert calls and calls[0]["name"] == "get_weather" and calls[0]["arguments"] == {"city": "Paris"}
    assert results and results[0]["result"]["city"] == "Paris"
    assert events[-1]["ok"] and second[-1]["text"] == "[mock] again"
