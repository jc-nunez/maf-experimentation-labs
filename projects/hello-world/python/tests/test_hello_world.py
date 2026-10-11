"""Offline tests (mock provider): tools directly, and agents/workflows end to end."""

from pathlib import Path

import pytest
from maf_labs_host import create_runner, load_project
from maf_labs_host.events import collect

PROJECT = load_project(Path(__file__).resolve().parents[2])


async def test_weather_tool_is_deterministic():
    from hello_world.tools.weather import get_weather

    result = await get_weather.invoke(arguments={"city": "Paris"}, skip_parsing=True)
    assert result["forecast"] == "sunny"


@pytest.mark.parametrize("target", ["greeter", "greeter-yaml"])
async def test_agent_calls_tool_with_mock(target):
    runner = create_runner(PROJECT, target, provider="mock")
    await runner.start()
    events = await collect(runner.turn('weather please\ncall:get_weather {"city": "Paris"}'))
    types = [e["type"] for e in events]
    assert "reasoning_delta" in types
    calls = [e for e in events if e["type"] == "tool_call"]
    results = [e for e in events if e["type"] == "tool_result"]
    assert calls[0]["name"] == "get_weather" and calls[0]["arguments"] == {"city": "Paris"}
    assert results[0]["result"]["forecast"] == "sunny"
    assert events[-1]["type"] == "turn_completed" and events[-1]["ok"]
    await runner.close()


async def test_session_keeps_history():
    runner = create_runner(PROJECT, "greeter", provider="mock")
    await runner.start()
    await collect(runner.turn("first"))
    events = await collect(runner.turn("second"))
    assert events[-1]["text"] == "[mock] second"
    await runner.close()


async def test_draft_review_workflow_runs_both_agents():
    runner = create_runner(PROJECT, "draft-review", provider="mock")
    await runner.start()
    events = await collect(runner.turn("Write a haiku about agents"))
    started = [e["executor_id"] for e in events if e["type"] == "executor_started"]
    assert "writer" in started and "reviewer" in started
    assert events[-1]["ok"], events
    await runner.close()


async def test_declarative_workflow():
    runner = create_runner(PROJECT, "greeting-flow", provider="mock")
    await runner.start()
    events = await collect(runner.turn("hi"))
    assert events[-1]["ok"], events
    assert "Hello" in events[-1]["text"]
    await runner.close()
