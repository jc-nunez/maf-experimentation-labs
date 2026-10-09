"""Rich renderer for trajectory events — reasoning, tool calls, workflow steps, usage.

Views: ``full`` (everything, untruncated), ``normal`` (long blocks folded), ``quiet`` (answer + one line per
tool call).

Layout: everything is indented under a two-space margin; every block (thinking, a group of tool calls, the
answer, the turn summary) is separated by exactly one blank line. Streaming text is rendered through a small live
region that only holds the paragraph still being written; finished paragraphs are printed permanently, so
wrapped lines keep their indentation and long answers never re-render (or duplicate) in the scrollback.
"""

from __future__ import annotations

import contextlib
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.console import Console, ConsoleOptions, RenderableType, RenderResult
from rich.live import Live
from rich.markdown import Markdown
from rich.markup import escape
from rich.padding import Padding
from rich.segment import Segment
from rich.syntax import Syntax
from rich.text import Text

VIEWS = ("full", "normal", "quiet")
FOLD_LINES = 12
MARGIN = 2  # left margin for headers
BODY = 4  # left margin for block contents


def _pad(renderable: RenderableType, pad: tuple[int, int, int, int]) -> Padding:
    """Left-indent without padding lines to the full width (no trailing spaces when copying text)."""
    return Padding(renderable, pad, expand=False)


def _json(value: Any) -> str:
    if isinstance(value, str):
        return value
    compact = json.dumps(value, ensure_ascii=False, default=str)
    if len(compact) <= 100:
        return compact
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


_FENCE = re.compile(r"^\s*(```|~~~)", re.MULTILINE)


def _markdown_boundary(text: str) -> int:
    """Index after the last paragraph break that is not inside a code fence (0 if none)."""
    cut = 0
    for match in re.finditer(r"\n\s*\n", text):
        if len(_FENCE.findall(text[: match.start()])) % 2 == 0:
            cut = match.end()
    return cut


def _line_boundary(text: str) -> int:
    return text.rfind("\n") + 1


class _Trimmed:
    """Render something without its leading/trailing blank lines (the renderer owns spacing between blocks)."""

    def __init__(self, renderable: RenderableType) -> None:
        self.renderable = renderable

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        lines = console.render_lines(self.renderable, options, pad=False)

        def blank(line: list[Segment]) -> bool:
            return not "".join(segment.text for segment in line).strip()

        while lines and blank(lines[0]):
            lines.pop(0)
        while lines and blank(lines[-1]):
            lines.pop()
        for line in lines:
            yield from line
            yield Segment.line()


class StreamBlock:
    """Streams text into the terminal: completed segments are printed permanently, the open one is live."""

    def __init__(
        self,
        console: Console,
        render: Callable[[str], RenderableType],
        boundary: Callable[[str], int],
        live: bool,
        on_start: Callable[[], None] | None = None,
        paragraph_gap: bool = False,
    ) -> None:
        self.console = console
        self.render = render
        self.boundary = boundary
        self.use_live = live
        self.on_start = on_start
        self.paragraph_gap = paragraph_gap  # markdown: keep the blank line between flushed paragraphs
        self.text = ""  # everything received (for folding / final output)
        self._open = ""  # not yet printed permanently
        self._printed = False
        self._live: Live | None = None

    @property
    def started(self) -> bool:
        return bool(self.text)

    def feed(self, piece: str) -> None:
        if not self.text and not piece.strip():
            return  # models often start with blank lines, or send whitespace-only blocks
        if not self.text:
            piece = piece.lstrip("\n")
            if self.on_start is not None:
                self.on_start()
        self.text += piece
        self._open += piece
        cut = self.boundary(self._open)
        if cut:
            done, self._open = self._open[:cut], self._open[cut:]
            self._print(done.rstrip("\n"))
        if self.use_live and self._open:
            if self._live is None:
                self._live = Live(console=self.console, refresh_per_second=12, transient=True, auto_refresh=True)
                self._live.start()
            self._live.update(self.render(self._open))

    def _print(self, segment: str) -> None:
        if self._live is not None:
            self._live.update(Text(""))
            self._live.stop()
            self._live = None
        if segment.strip():
            self._emit(segment)

    def _emit(self, segment: str) -> None:
        if self._printed and self.paragraph_gap:
            self.console.print()
        self.console.print(self.render(segment))
        self._printed = True

    def close(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None
        tail, self._open = self._open.strip("\n"), ""
        if tail.strip():
            self._emit(tail)


class Renderer:
    def __init__(self, console: Console, view: str = "full", markdown: bool = True, show_text: bool = True) -> None:
        self.console = console
        self.view = view
        self.live = console.is_terminal
        self.markdown = markdown and console.is_terminal
        self.show_text = show_text  # False in -p mode: answer goes to stdout separately
        self._block: str | None = None  # "reasoning" | "text" | "tools"
        self._block_executor: str | None = None
        self._stream: StreamBlock | None = None
        self._folded: list[str] = []  # reasoning collected in "normal" view, shown as one line
        self._calls: dict[str, dict[str, Any]] = {}
        self._paused: dict[str, float] = {}  # totals of turn parts that stopped for approvals
        self._blank = False  # was the last line printed blank? (start with a gap after the header/prompt)

    # ------------------------------------------------------------------------------------------ helpers

    def _print(self, renderable: RenderableType = "", indent: int = MARGIN) -> None:
        if renderable == "":
            self.console.print()
            self._blank = True
            return
        self.console.print(_pad(renderable, (0, 0, 0, indent)) if indent else renderable)
        self._blank = False

    def _gap(self) -> None:
        """Exactly one blank line between blocks."""
        if not self._blank:
            self._print()

    def _body(self, label: str, value: Any, style: str = "") -> None:
        text = _json(value)
        lines = text.splitlines() or [""]
        if self.view == "normal" and len(lines) > FOLD_LINES:
            lines = [*lines[:FOLD_LINES], f"… +{len(lines) - FOLD_LINES} lines (/view full)"]
        body = Text(label, style="dim") + Text("\n".join(lines), style=style)
        self._print(body, indent=BODY)

    # ------------------------------------------------------------------------------------------ blocks

    def _end_block(self) -> None:
        if self._stream is not None:
            self._stream.close()
            if self._stream.started:
                self._blank = False
            self._stream = None
        if self._block == "reasoning" and self.view == "normal" and "".join(self._folded).strip():
            self._gap()
            label = f"[{self._block_executor}] " if self._block_executor else ""
            self._print(Text(f"✻ {label}Thinking", style="magenta"))
            lines = "".join(self._folded).strip().splitlines()
            first = lines[0] if lines else ""
            more = f" … (+{len(lines) - 1} lines, /view full)" if len(lines) > 1 else ""
            self._print(Text(first + more, style="dim italic"), indent=BODY)
            self._folded = []
        self._block = None
        self._block_executor = None

    def _start_block(self, kind: str, executor: str | None) -> None:
        if self._block == kind and self._block_executor == executor:
            return
        self._end_block()
        self._block = kind
        self._block_executor = executor
        label = f"[{executor}] " if executor else ""
        if kind == "reasoning":
            if self.view == "full":

                def header() -> None:
                    self._gap()
                    self._print(Text(f"✻ {label}Thinking", style="magenta"))

                self._stream = StreamBlock(
                    self.console,
                    lambda s: _pad(Text(s, style="dim italic"), (0, 0, 0, BODY)),
                    _line_boundary,
                    self.live,
                    on_start=header,
                )
        elif kind == "text":
            if not self.show_text:
                return

            def text_header() -> None:
                self._gap()
                if label:
                    self._print(Text(label.strip(), style="bold cyan"))

            if self.markdown:
                render: Callable[[str], RenderableType] = lambda s: _pad(  # noqa: E731
                    _Trimmed(Markdown(s)), (0, 0, 0, MARGIN)
                )
                self._stream = StreamBlock(
                    self.console, render, _markdown_boundary, self.live, on_start=text_header, paragraph_gap=True
                )
            else:
                self._stream = StreamBlock(
                    self.console,
                    lambda s: _pad(Text(s), (0, 0, 0, MARGIN)),
                    _line_boundary,
                    live=False,
                    on_start=text_header,
                )
        elif kind == "tools":
            self._gap()

    # ------------------------------------------------------------------------------------------ events

    def handle(self, e: dict[str, Any]) -> None:
        t = e["type"]
        executor = e.get("executor_id")

        if t == "reasoning_delta":
            self._start_block("reasoning", executor)
            if self._stream is not None:
                self._stream.feed(e["text"])
            elif self.view == "normal":
                self._folded.append(e["text"])
            return
        if t == "text_delta":
            self._start_block("text", executor)
            if self._stream is not None:
                self._stream.feed(e["text"])
            return
        if t in ("tool_call", "tool_result"):
            self._start_block("tools", executor)
        elif t not in ("usage",):
            self._end_block()

        prefix = f"[{executor}] " if executor else ""

        if t == "tool_call":
            self._calls[e["call_id"]] = e
            args = e.get("arguments")
            if self.view == "quiet":
                compact = json.dumps(args, ensure_ascii=False, default=str)
                self._print(Text(f"⏺ {prefix}{e['name']}({compact})", style="yellow"))
                return
            self._print(
                Text("⏺ ", style="yellow")
                + Text(f"{prefix}{e['name']}", style="bold yellow")
                + Text(f"  {e['call_id']}", style="dim")
            )
            self._body("args   ", args)
        elif t == "tool_result":
            failed = bool(e.get("error"))
            if self.view == "quiet":
                if failed:
                    self._print(Text(f"  ⎿ error: {e['error']}", style="red"))
                return
            took = f"  ·  {e['duration_s']}s" if e.get("duration_s") is not None else ""
            call = self._calls.get(e.get("call_id") or "", {})
            self._print(
                Text("⎿ ", style="red" if failed else "green")
                + Text(f"{prefix}{call.get('name', 'result')}", style="bold")
                + Text(f"  {e.get('call_id')}{took}", style="dim")
            )
            if failed:
                self._body("error  ", e["error"], style="red")
            else:
                self._body("result ", e.get("result"))
        elif t == "approval_request":
            self._gap()
            self._print(
                Text("🔐 ", style="yellow")
                + Text(f"{prefix}{e.get('name')}", style="bold yellow")
                + Text("  needs approval", style="yellow")
            )
            self._body("args   ", e.get("arguments"))
        elif t == "approval_decision":
            ok = e.get("decision") != "deny"
            labels = {
                "approve": "approved",
                "always": "approved for this session",
                "always_args": "approved for these arguments",
                "deny": "denied",
            }
            self._print(
                Text("✓ " if ok else "✗ ", style="green" if ok else "red")
                + Text(f"{e.get('name')} {labels.get(e.get('decision'), e.get('decision'))}", style="dim")
            )
        elif t == "executor_started":
            self._gap()
            self.console.rule(Text(f"▶ {executor}", style="bold cyan"), align="left", style="cyan")
            self._blank = False
            if self.view == "full" and e.get("input") not in (None, ""):
                self._body("input  ", e["input"], style="dim")
        elif t == "executor_completed":
            if self.view != "quiet":
                self._gap()
                self._print(Text(f"✓ {executor}", style="green"))
        elif t == "workflow_output":
            if self.view != "quiet":
                self._gap()
                self._print(Text(f"◆ {prefix}output", style="bold green"))
                self._body("", e.get("data"))
        elif t == "request_info":
            self._gap()
            self._print(
                Text(f"? {prefix}input requested", style="bold magenta") + Text(f"  {e.get('request_id')}", style="dim")
            )
            self._body("", e.get("data"))
            self._print(Text("reply in the next message to continue the workflow", style="dim"), indent=BODY)
        elif t == "warning":
            self._gap()
            self._print(Text(f"⚠ {prefix}{e.get('message')}", style="yellow"))
        elif t == "error":
            self._gap()
            self._print(Text(f"✗ {prefix}{e.get('message')}", style="bold red"))
        elif t == "turn_completed":
            keys = ("model_calls", "tool_calls", "input_tokens", "output_tokens", "duration_s")
            if e.get("pending_approvals"):
                # Not the end of the turn: it continues after the approval decisions. Summarise once, at the end.
                for k in keys:
                    self._paused[k] = self._paused.get(k, 0) + (e.get(k) or 0)
                return
            if self._paused:
                e = {**e, **{k: (e.get(k) or 0) + self._paused.get(k, 0) for k in keys}}
                e["duration_s"] = round(e["duration_s"], 3)
                self._paused = {}
            self._gap()
            ok = e.get("ok")
            summary = (
                f"{_plural(e.get('model_calls', 0), 'model call')} · {_plural(e.get('tool_calls', 0), 'tool call')} · "
                f"in {e.get('input_tokens', 0):,} / out {e.get('output_tokens', 0):,} tok · {e.get('duration_s', 0)}s"
            )
            self._print(Text(summary + ("" if ok else " · failed"), style="dim" if ok else "red"))

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
