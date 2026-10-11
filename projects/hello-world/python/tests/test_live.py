"""Live tests against the configured endpoint: uv run pytest -m live (reads .env)."""

import os
from pathlib import Path

import pytest
from maf_labs_host import create_runner, find_workspace, load_project
from maf_labs_host.events import collect
from maf_labs_host.workspace import load_env

ROOT = Path(__file__).resolve().parents[2]
load_env(find_workspace(ROOT), ROOT)
PROJECT = load_project(ROOT)

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("SGLANG_BASE_URL") and os.environ.get("MAF_PROVIDER") in (None, "sglang"),
        reason="no endpoint configured (.env)",
    ),
]


@pytest.mark.parametrize("target", ["greeter", "greeter-yaml"])
async def test_greeter_uses_weather_tool(target):
    runner = create_runner(PROJECT, target)
    await runner.start()
    events = await collect(runner.turn("What's the weather in Paris? Use your tool."))
    await runner.close()
    done = events[-1]
    assert done["ok"], [e for e in events if e["type"] == "error"]
    calls = [e for e in events if e["type"] == "tool_call"]
    assert any(c["name"] == "get_weather" for c in calls), "model did not call get_weather (check tool-call parser)"
    assert "22" in done["text"] or "sunny" in done["text"].lower()


async def test_draft_review_workflow():
    runner = create_runner(PROJECT, "draft-review")
    await runner.start()
    events = await collect(runner.turn("Write a two-line poem about tests."))
    await runner.close()
    assert events[-1]["ok"] and events[-1]["text"].strip()
