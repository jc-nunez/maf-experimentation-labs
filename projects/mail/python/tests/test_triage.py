"""Triage agent end to end on the mock provider: the tool runs against Graph fixtures (no network)."""

from pathlib import Path

from maf_labs_host import create_runner, load_project
from maf_labs_host.events import collect

PROJECT = load_project(Path(__file__).resolve().parents[2])


async def test_triage_calls_mail_digest(graph_mock):
    runner = create_runner(PROJECT, "triage", provider="mock")
    await runner.start()
    events = await collect(runner.turn('last 7 days\ncall:mail_digest {"account": "personal", "days": 7}'))
    calls = [e for e in events if e["type"] == "tool_call"]
    results = [e for e in events if e["type"] == "tool_result"]
    assert calls[0]["name"] == "mail_digest" and calls[0]["arguments"] == {"account": "personal", "days": 7}
    assert results[0]["result"]["total"] == 5
    assert results[0]["result"]["senders"][0]["address"] == "orders@shop.example"
    assert events[-1]["type"] == "turn_completed" and events[-1]["ok"]
    await runner.close()


def test_project_is_read_only():
    """A6: the only tool is mail_digest, and the triage agent only gets that tool."""
    assert [t.name for t in PROJECT.components.tools] == ["mail-digest"]
    assert PROJECT.components.agents[0].tools == ["mail-digest"]
    assert PROJECT.components.agents[0].reasoning_effort == "low"
