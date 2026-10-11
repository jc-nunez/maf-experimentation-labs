"""Offline smoke test: every agent/workflow in the manifest builds and runs on the mock provider."""

from pathlib import Path

import pytest
from maf_labs_host import create_runner, load_project
from maf_labs_host.events import collect

PROJECT = load_project(Path(__file__).resolve().parents[2])
TARGETS = [s.name for k in ("agents", "workflows") for s in getattr(PROJECT.components, k) if s.runtime != "dotnet"]


@pytest.mark.parametrize("target", TARGETS or [pytest.param(None, marks=pytest.mark.skip("no components yet"))])
async def test_runs_on_mock(target):
    runner = create_runner(PROJECT, target, provider="mock")
    await runner.start()
    events = await collect(runner.turn("hello"))
    assert events[-1]["type"] == "turn_completed" and events[-1]["ok"], events
    await runner.close()
