"""Rich renderer for trajectory events — reasoning, tool calls, workflow steps, usage.

Views: ``full`` (everything, untruncated), ``normal`` (long blocks folded), ``quiet`` (answer + one line per
tool call).
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.markup import escape
from rich.syntax import Syntax
from rich.text import Text

VIEWS = ("full", "normal", "quiet")
FOLD_LINES = 12


def _json(value: Any) -> str:
    if isinstance(value, str):
        return value
    compact = json.dumps(value, ensure_ascii=False, default=str)
    if len(compact) <= 100:
        return compact
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


class Renderer:
    def __init__(self, console: Console, view: str = "full", markdown: bool = True, show_text: bool = True) -> None:
        self.console = console
        self.view = view
        self.markdown = markdown and console.is_terminal
        self.show_text = show_text  # False in -p mode: answer goes to stdout separately
        self._block: str | None = None  # "reasoning" | "text"
        self._block_executor: str | None = None
        self._buf: list[str] = []
        self._live: Live | None = None
        self._reasoning_tokens = 0
        self._calls: dict[str, dict[str, Any]] = {}
        self._at_line_start = True

    # ------------------------------------------------------------------------------------------ blocks

    def _end_block(self) -> None:
        if self._block == "text":
            if self._live is not None:
                self._live.update(Markdown("".join(self._buf)))
                self._live.stop()
                self._live = None
            elif not self.markdown:
                self.console.print()
        elif self._block == "reasoning":
            if self.view == "normal":
                text = "".join(self._buf).strip().splitlines()
                first = text[0] if text else ""
                more = f" … (+{len(text) - 1} lines, /view full)" if len(text) > 1 else ""
                self.console.print(Text("  │ ", style="dim") + Text(first + more, style="dim italic"))
            else:
                self.console.print()
        self._block = None
        self._buf = []
        self._at_line_start = True

    def _start_block(self, kind: str, executor: str | None) -> None:
        if self._block == kind and self._block_executor == executor:
            return
        self._end_block()
        self._block = kind
        self._block_executor = executor
        prefix = f"[{executor}] " if executor else ""
        if kind == "reasoning" and self.view != "quiet":
            self.console.print(Text(f"  ✻ {prefix}Thinking", style="magenta"))
        elif kind == "text" and self.show_text:
            if prefix:
                self.console.print(Text(f"  {prefix.strip()}", style="bold cyan"))
            if self.markdown:
                self._live = Live(
                    Markdown(""), console=self.console, refresh_per_second=12, vertical_overflow="visible"
                )
                self._live.start()

    def _stream_reasoning(self, piece: str) -> None:
        self._buf.append(piece)
        if self.view != "full":
            return
        out = Text()
        for i, part in enumerate(piece.split("\n")):
            if i > 0:
                out.append("\n")
                self._at_line_start = True
            if part:
                if self._at_line_start:
                    out.append("  │ ", style="dim")
                    self._at_line_start = False
                out.append(part, style="dim italic")
        self.console.print(out, end="")

    def _stream_text(self, piece: str) -> None:
        self._buf.append(piece)
        if not self.show_text:
            return
        if self._live is not None:
            self._live.update(Markdown("".join(self._buf)))
        else:
            self.console.print(piece, end="", markup=False, highlight=False)

    # ------------------------------------------------------------------------------------------ events

    def _body(self, label: str, value: Any, style: str = "") -> None:
        text = _json(value)
        lines = text.splitlines() or [""]
        if self.view == "normal" and len(lines) > FOLD_LINES:
            lines = [*lines[:FOLD_LINES], f"… +{len(lines) - FOLD_LINES} lines (/view full)"]
        pad = " " * len(label)
        for i, line in enumerate(lines):
            head = label if i == 0 else pad
            self.console.print(Text("  │ ", style="dim") + Text(head, style="dim") + Text(line, style=style))

    def handle(self, e: dict[str, Any]) -> None:
        t = e["type"]
        executor = e.get("executor_id")

        if t == "reasoning_delta":
            self._start_block("reasoning", executor)
            if self.view != "quiet":
                self._stream_reasoning(e["text"])
            return
        if t == "text_delta":
            self._start_block("text", executor)
            self._stream_text(e["text"])
            return

        self._end_block()
        prefix = f"[{executor}] " if executor else ""

        if t == "tool_call":
            self._calls[e["call_id"]] = e
            args = e.get("arguments")
            if self.view == "quiet":
                compact = json.dumps(args, ensure_ascii=False, default=str)
                self.console.print(Text(f"  ⏺ {prefix}{e['name']}({compact})", style="yellow"))
                return
            self.console.print(
                Text("  ⏺ ", style="yellow")
                + Text(f"{prefix}{e['name']}", style="bold yellow")
                + Text(f"  {e['call_id']}", style="dim")
            )
            self._body("args   ", args)
        elif t == "tool_result":
            if self.view == "quiet":
                if e.get("error"):
                    self.console.print(Text(f"    ⎿ error: {e['error']}", style="red"))
                return
            took = f"  ·  {e['duration_s']}s" if e.get("duration_s") is not None else ""
            call = self._calls.get(e.get("call_id") or "", {})
            failed = bool(e.get("error"))
            self.console.print(
                Text("  ⎿ ", style="red" if failed else "green")
                + Text(f"{prefix}{call.get('name', 'result')}", style="bold")
                + Text(f"  {e.get('call_id')}{took}", style="dim")
            )
            if failed:
                self._body("error  ", e["error"], style="red")
            else:
                self._body("result ", e.get("result"))
        elif t == "executor_started":
            self.console.rule(Text(f"▶ {executor}", style="bold cyan"), align="left", style="cyan")
            if self.view == "full" and e.get("input") not in (None, ""):
                self._body("input  ", e["input"], style="dim")
        elif t == "executor_completed":
            if self.view != "quiet":
                self.console.print(Text(f"  ✓ {executor}", style="green"))
        elif t == "workflow_output":
            if self.view != "quiet":
                self.console.print(Text(f"  ◆ {prefix}output", style="bold green"))
                self._body("       ", e.get("data"))
        elif t == "request_info":
            self.console.print(
                Text(f"  ? {prefix}input requested", style="bold magenta")
                + Text(f"  {e.get('request_id')}", style="dim")
            )
            self._body("       ", e.get("data"))
            self.console.print(Text("    reply in the next message to continue the workflow", style="dim"))
        elif t == "usage":
            pass  # summarised in turn_completed
        elif t == "warning":
            self.console.print(Text(f"  ⚠ {prefix}{e.get('message')}", style="yellow"))
        elif t == "error":
            self.console.print(Text(f"  ✗ {prefix}{e.get('message')}", style="bold red"))
        elif t == "turn_completed":
            status = "" if e.get("ok") else " · failed"
            self.console.rule(
                Text(
                    f"{e.get('model_calls', 0)} model calls · {e.get('tool_calls', 0)} tool calls · "
                    f"in {e.get('input_tokens', 0):,} / out {e.get('output_tokens', 0):,} tok · "
                    f"{e.get('duration_s', 0)}s{status}",
                    style="dim" if e.get("ok") else "red",
                ),
                style="dim",
                align="right",
            )

    def finish(self) -> None:
        self._end_block()


def print_info(console: Console, info: dict[str, Any]) -> None:
    """Session header: what is running, on which model, with which tools."""
    head = (
        Text("╭─ ", style="dim")
        + Text(info.get("target", "?"), style="bold")
        + Text(
            f"  ·  {info.get('runtime')}  ·  {info.get('provider')} ({info.get('api')})  ·  {info.get('model')}"
            f"  ·  effort {info.get('effort', 'default')}",
            style="dim",
        )
    )
    console.print(head)
    if info.get("tools"):
        console.print(Text("│  tools: ", style="dim") + Text(", ".join(info["tools"])))
    if info.get("executors"):
        console.print(Text("│  executors: ", style="dim") + Text(" → ".join(info["executors"])))
    if info.get("trace"):
        trace = Path(info["trace"])
        with contextlib.suppress(ValueError):
            trace = trace.relative_to(Path.cwd())
        console.print(Text(f"│  trace: {trace}", style="dim"), overflow="fold")
    console.print(Text("╰─", style="dim"))


def print_instructions(console: Console, info: dict[str, Any]) -> None:
    if info.get("instructions"):
        console.print(Text("system prompt", style="bold"))
        console.print(Syntax(info["instructions"], "markdown", word_wrap=True, background_color="default"))
    else:
        console.print(escape("(no instructions reported by this runtime)"))
