"""Unit tests for the shared host: manifest validation, event translation, stdio protocol."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from agent_framework import AgentResponseUpdate, Content
from maf_labs_host.events import UpdateTranslator
from maf_labs_host.manifest import Project, ToolSpec
from maf_labs_host.providers import ProviderConfigError, create_chat_client
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[4]


def test_python_component_requires_entry():
    with pytest.raises(ValidationError, match="entry"):
        Project.model_validate({"name": "x", "components": {"agents": [{"name": "a", "runtime": "python"}]}})


def test_mcp_tool_transport_is_inferred():
    assert ToolSpec(name="t", kind="mcp", url="http://localhost/mcp").transport == "http"
    with pytest.raises(ValidationError, match="command"):
        ToolSpec(name="t", kind="mcp", transport="stdio")


def test_unknown_manifest_keys_are_rejected():
    with pytest.raises(ValidationError):
        Project.model_validate({"name": "x", "agentz": []})


def test_translator_merges_streamed_function_call_arguments():
    tr = UpdateTranslator()
    events = []
    for piece in ['{"ci', 'ty": "Pa', 'ris"}']:
        update = AgentResponseUpdate(
            contents=[Content.from_function_call(call_id="c1", name="get_weather", arguments=piece)]
        )
        events += tr.translate(update)
    assert events == []  # buffered until something else arrives
    events += tr.translate(AgentResponseUpdate(contents=[Content.from_function_result(call_id="c1", result="ok")]))
    assert [e["type"] for e in events] == ["tool_call", "tool_result"]
    assert events[0]["arguments"] == {"city": "Paris"}
    assert tr.tool_calls == 1


def test_translator_strips_leading_whitespace_of_the_reply():
    tr = UpdateTranslator()
    events = []
    for piece in ["\n\n", "  \n", "Hello", "\n\nworld  "]:
        events += tr.translate(AgentResponseUpdate(contents=[Content.from_text(text=piece)]))
    assert [e["text"] for e in events] == ["Hello", "\n\nworld  "]
    assert tr.text == "Hello\n\nworld  "


def test_sglang_requires_base_url(monkeypatch):
    monkeypatch.delenv("SGLANG_BASE_URL", raising=False)
    with pytest.raises(ProviderConfigError, match="SGLANG_BASE_URL"):
        create_chat_client("sglang")


def test_sglang_defaults_to_client_side_history(monkeypatch):
    monkeypatch.setenv("SGLANG_BASE_URL", "http://localhost:30000/v1")
    monkeypatch.setenv("SGLANG_MODEL", "some/model")
    monkeypatch.delenv("SGLANG_STORE", raising=False)
    monkeypatch.delenv("SGLANG_API", raising=False)
    _, info = create_chat_client("sglang")
    assert info.api == "responses" and info.default_options == {"store": False}


def test_stdio_protocol_round_trip():
    """The JSONL protocol mafx uses for out-of-process hosts (python here; .NET implements the same)."""
    proc = subprocess.run(
        [sys.executable, "-m", "hello_world", "greeter", "--stdio", "--provider", "mock", "--no-trace"],
        input=json.dumps({"type": "user", "text": "hi"}) + "\n" + json.dumps({"type": "exit"}) + "\n",
        capture_output=True,
        text=True,
        cwd=ROOT / "projects/hello-world",
        timeout=60,
    )
    lines = [json.loads(line) for line in proc.stdout.splitlines()]
    assert lines[0]["type"] == "ready" and lines[0]["info"]["target"] == "hello-world/greeter"
    assert lines[-1]["type"] == "turn_completed" and lines[-1]["text"] == "[mock] hi"


async def test_sglang_client_never_replays_reasoning(monkeypatch):
    """SGLang returns reasoning without encrypted_content, so it must not be replayed (it would be rejected)."""
    from agent_framework import Message
    from agent_framework.openai import OpenAIChatClient
    from maf_labs_host.providers import SGLangResponsesClient

    sent = {}

    def fake_inner(self, *, messages, options, stream=False, **kwargs):
        sent["messages"] = messages

    monkeypatch.setattr(OpenAIChatClient, "_inner_get_response", fake_inner)
    history = [
        Message("user", ["weather?"]),
        Message(
            "assistant",
            [
                Content.from_text_reasoning(id="rs_1", text="call the tool"),
                Content.from_function_call(call_id="c1", name="get_weather", arguments="{}"),
            ],
        ),
        Message("tool", [Content.from_function_result(call_id="c1", result="sunny")]),
    ]
    client = SGLangResponsesClient(model="m", api_key="k", base_url="http://localhost/v1")
    client._inner_get_response(messages=history, options={})
    assert [c.type for c in sent["messages"][1].contents] == ["function_call"]
    assert sent["messages"][0] is history[0] and sent["messages"][2] is history[2]
    assert any(c.type == "text_reasoning" for c in history[1].contents)  # session history untouched


async def test_reasoning_effort_manifest_default_and_run_override():
    from maf_labs_host import create_runner, load_project

    project = load_project(ROOT / "projects/hello-world")
    runner = create_runner(project, "greeter", provider="mock")
    await runner.start()
    assert runner.agent.default_options["reasoning"] == {"effort": "low"}  # from project.yaml
    assert runner.info["effort"] == "low"
    await runner.set_effort("none")
    assert runner.info["effort"] == "none"
    await runner.set_effort(None)
    assert runner.info["effort"] == "low"
    overridden = create_runner(project, "greeter", provider="mock", reasoning_effort="xhigh")
    await overridden.start()
    assert overridden.info["effort"] == "xhigh"


def test_unknown_reasoning_effort_is_rejected():
    with pytest.raises(ValidationError):
        Project.model_validate(
            {"name": "x", "components": {"agents": [{"name": "a", "entry": "m:f", "reasoning_effort": "max"}]}}
        )
