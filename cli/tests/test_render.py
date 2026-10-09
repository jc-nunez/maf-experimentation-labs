"""Renderer layout rules: one blank line between blocks, no phantom blocks, trimmed markdown."""

import io

from mafx.render import Renderer, _markdown_boundary, _Trimmed
from rich.console import Console
from rich.markdown import Markdown


def render(events, view="full"):
    out = io.StringIO()
    console = Console(file=out, width=80, force_terminal=False, color_system=None)
    r = Renderer(console, view=view)
    for e in events:
        r.handle(e)
    r.finish()
    return out.getvalue()


def test_whitespace_only_text_between_reasoning_and_tools_adds_no_gap():
    text = render(
        [
            {"type": "reasoning_delta", "text": "I will call the tool.\n"},
            {"type": "text_delta", "text": "\n\n"},  # Qwen sends this before tool calls
            {"type": "tool_call", "call_id": "c1", "name": "get_weather", "arguments": {"city": "Paris"}},
        ]
    )
    assert "I will call the tool.\n\n  ⏺ get_weather" in text


def test_blocks_are_separated_by_exactly_one_blank_line():
    text = render(
        [
            {"type": "reasoning_delta", "text": "thinking"},
            {"type": "tool_call", "call_id": "c1", "name": "t", "arguments": {}},
            {"type": "tool_result", "call_id": "c1", "result": "ok"},
            {"type": "text_delta", "text": "\n\nThe answer."},
            {"type": "turn_completed", "ok": True, "model_calls": 2, "tool_calls": 1},
        ]
    )
    assert "\n\n\n" not in text
    assert "The answer.\n\n  2 model calls · 1 tool call" in text


def test_reasoning_wraps_with_indentation():
    long = "word " * 40
    text = render([{"type": "reasoning_delta", "text": long}])
    body = [line for line in text.splitlines() if "word" in line]
    assert len(body) > 1 and all(line.startswith("    word") for line in body)


def test_markdown_boundary_ignores_breaks_inside_code_fences():
    assert _markdown_boundary("para one\n\n```\ncode\n\nmore\n") == len("para one\n\n")


def test_trimmed_markdown_has_no_outer_blank_lines():
    out = io.StringIO()
    Console(file=out, width=60, color_system=None).print(_Trimmed(Markdown("| a | b |\n|---|---|\n| 1 | 2 |")))
    lines = out.getvalue().splitlines()
    assert lines[0].strip() and lines[-1].strip()
