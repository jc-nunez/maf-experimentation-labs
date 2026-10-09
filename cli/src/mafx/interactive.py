"""Interactive session: agentic-CLI style input box, streaming trajectory, slash commands."""

from __future__ import annotations

import asyncio
import contextlib
import signal
from pathlib import Path
from typing import Any

from maf_labs_host.approvals import drive
from maf_labs_host.runner import Runner
from prompt_toolkit.application import Application, get_app
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.filters import has_completions
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import ConditionalContainer, HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.menus import CompletionsMenuControl
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea
from prompt_toolkit.widgets.base import Border
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .render import VIEWS, Renderer, print_info, print_instructions

COMMANDS = {
    "/help": "show this help",
    "/reset": "start a new session (clears history)",
    "/retry": "re-run the last prompt",
    "/view": "full | normal | quiet — how much of the trajectory to show",
    "/effort": "none | low | medium | xhigh | default — reasoning effort for the next turns",
    "/info": "target, provider, model, tools, trace file",
    "/system": "show the agent's instructions",
    "/trace": "print the path of this run's trace.jsonl",
    "/clear": "clear the screen",
    "/exit": "quit (also Ctrl+D)",
}

STYLE = Style.from_dict(
    {
        "prompt": "ansicyan bold",
        "frame.border": "ansibrightblack",
        "toolbar": "ansibrightblack",
        "approval": "ansiyellow bold",
        "toolbar.key": "ansibrightblack bold",
        "completion-menu": "bg:ansibrightblack ansiwhite",
        "completion-menu.completion.current": "bg:ansicyan ansiblack",
    }
)

# Bare words people type by habit; treated as the slash command when they are the whole input.
BARE_COMMANDS = {"exit", "quit", "clear", "help"}


def _round_frame_corners() -> None:
    """Match the rounded panels Rich draws for echoed messages."""
    Border.TOP_LEFT, Border.TOP_RIGHT, Border.BOTTOM_LEFT, Border.BOTTOM_RIGHT = "╭", "╮", "╰", "╯"


class InputBox:
    """Inline (non full-screen) input: a framed, growing text area, completion menu and status line.

    The whole widget is drawn and erased by prompt_toolkit, so nothing is left half-drawn in the scrollback;
    the session echoes the submitted message afterwards as a static panel.
    """

    def __init__(self, history: FileHistory, toolbar: Any) -> None:
        self.area = TextArea(
            prompt=[("class:prompt", " › ")],
            multiline=True,
            wrap_lines=True,
            history=history,
            completer=WordCompleter(list(COMMANDS), meta_dict=COMMANDS, sentence=True),
            complete_while_typing=True,
            dont_extend_height=True,
            get_line_prefix=lambda line, wrap: "" if line == 0 and wrap == 0 else "   ",
        )
        kb = KeyBindings()

        @kb.add("enter")
        def _submit(event: Any) -> None:
            buf = self.area.buffer
            if buf.complete_state and buf.complete_state.current_completion:
                buf.apply_completion(buf.complete_state.current_completion)
                return
            if buf.text.strip():
                buf.append_to_history()
            event.app.exit(result=buf.text)

        @kb.add("escape", "enter")  # Alt+Enter
        @kb.add("c-j")  # Ctrl+J (and Shift+Enter in many terminals)
        def _newline(event: Any) -> None:
            self.area.buffer.insert_text("\n")

        @kb.add("c-c")
        def _cancel(event: Any) -> None:
            event.app.exit(result="")

        @kb.add("c-d")
        def _eof(event: Any) -> None:
            if not self.area.buffer.text:
                event.app.exit(result=None)

        _round_frame_corners()
        root = HSplit(
            [
                Frame(self.area),
                # Suggestions open below the box (not drawn over its border).
                ConditionalContainer(
                    Window(CompletionsMenuControl(), height=self._menu_height, style="class:completion-menu"),
                    filter=has_completions,
                ),
                Window(FormattedTextControl(toolbar), height=1, style="class:toolbar"),
            ]
        )
        self.app: Application[str | None] = Application(
            layout=Layout(root, focused_element=self.area),
            key_bindings=kb,
            style=STYLE,
            full_screen=False,
            erase_when_done=True,
            mouse_support=False,
        )

    def _menu_height(self) -> Dimension:
        state = self.area.buffer.complete_state
        return Dimension.exact(min(6, max(1, len(state.completions) if state else 1)))

    async def read(self) -> str | None:
        self.area.buffer.reset()
        return await self.app.run_async()


APPROVAL_KEYS = {"y": "approve", "a": "always", "A": "always_args", "n": "deny"}


async def ask_approval(tool: str) -> str:
    """Single-key approval prompt: y approve · a always (tool) · A always (these args) · n deny. Ctrl+C denies."""
    kb = KeyBindings()

    for key, decision in APPROVAL_KEYS.items():

        @kb.add(key)
        def _choose(event: Any, decision: str = decision) -> None:
            event.app.exit(result=decision)

    @kb.add("enter")
    def _default(event: Any) -> None:
        event.app.exit(result="approve")

    @kb.add("c-c")
    @kb.add("escape")
    def _deny(event: Any) -> None:
        event.app.exit(result="deny")

    question = [
        ("class:approval", f"    Allow {tool}? "),
        ("class:toolbar.key", "y"),
        ("class:toolbar", " yes (⏎) · "),
        ("class:toolbar.key", "a"),
        ("class:toolbar", " always for this tool · "),
        ("class:toolbar.key", "A"),
        ("class:toolbar", " always with these args · "),
        ("class:toolbar.key", "n"),
        ("class:toolbar", " no"),
    ]
    app: Application[str] = Application(
        layout=Layout(Window(FormattedTextControl(question), height=1)),
        key_bindings=kb,
        style=STYLE,
        full_screen=False,
        erase_when_done=True,
    )
    return await app.run_async()


def _turns(n: int) -> str:
    return f"{n} turn" if n == 1 else f"{n} turns"


class Session:
    def __init__(
        self,
        runner: Runner,
        console: Console,
        view: str,
        history_dir: Path,
        approve_all: bool = False,
        allow_tools: list[str] | None = None,
    ) -> None:
        self.runner = runner
        self.approve_all = approve_all
        self.allow_tools = set(allow_tools or [])
        self.console = console
        self.view = view
        self.last_prompt: str | None = None
        self.turns = 0
        self.tokens_in = 0
        self.tokens_out = 0
        history_dir.mkdir(parents=True, exist_ok=True)
        safe = runner.target.replace("/", "__")
        self.input = InputBox(FileHistory(str(history_dir / f"{safe}.history")), self._toolbar)

    def _toolbar(self) -> list[tuple[str, str]]:
        info = self.runner.info
        model = str(info.get("model") or "?").rsplit("/", 1)[-1]
        status = (
            f" {model} · effort {info.get('effort', 'default')} · {_turns(self.turns)} · "
            f"{self.tokens_in:,} in / {self.tokens_out:,} out"
        )
        hints = [
            ("class:toolbar.key", "⏎"),
            ("class:toolbar", " send · "),
            ("class:toolbar.key", "Alt+⏎"),
            ("class:toolbar", " newline · "),
            ("class:toolbar.key", "/help"),
        ]
        width = get_app().output.get_size().columns
        hints_len = sum(len(t) for _, t in hints) + 3
        if len(status) + hints_len <= width:
            return [("class:toolbar", status + "   "), *hints]
        return [("class:toolbar", status)]

    async def _read(self) -> str | None:
        text = await self.input.read()
        if text and text.strip():
            # Two-column grid so wrapped and multi-line input hangs under the text, not under the "›".
            echo = Table.grid(padding=(0, 1))
            echo.add_column(style="bold cyan", no_wrap=True)
            echo.add_column(overflow="fold")
            echo.add_row("›", Text(text.strip()))
            self.console.print(Panel(echo, box=box.ROUNDED, border_style="bright_black", padding=(0, 1)))
        return text

    async def _turn(self, text: str) -> None:
        self.last_prompt = text
        renderer = Renderer(self.console, view=self.view)

        async def consume() -> None:
            async for e in drive(self.runner, self.runner.turn(text), self._decide):
                renderer.handle(e)
                if e["type"] == "turn_completed":
                    if not e.get("pending_approvals"):
                        self.turns += 1
                    self.tokens_in += e.get("input_tokens", 0)
                    self.tokens_out += e.get("output_tokens", 0)

        task = asyncio.ensure_future(consume())
        loop = asyncio.get_running_loop()
        with contextlib.suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(signal.SIGINT, task.cancel)
        try:
            await task
        except asyncio.CancelledError:
            renderer.finish()
            self.console.print(Text("  ⏹ interrupted", style="yellow"))
        finally:
            renderer.finish()
            with contextlib.suppress(NotImplementedError, RuntimeError):
                loop.remove_signal_handler(signal.SIGINT)

    async def _decide(self, pending: list[dict[str, Any]]) -> dict[str, str]:
        """Ask about each tool call waiting for approval (the request itself was already rendered)."""
        decisions: dict[str, str] = {}
        for request in pending:
            if self.approve_all or request["name"] in self.allow_tools:
                decisions[request["request_id"]] = "approve"
                continue
            answer = await ask_approval(request["name"])
            decisions[request["request_id"]] = answer
            if answer == "always":
                self.allow_tools.add(request["name"])
        return decisions

    async def _command(self, line: str) -> bool:
        """Handle a slash command. Returns False to exit."""
        cmd, _, arg = line.strip().partition(" ")
        if cmd in ("/exit", "/quit"):
            return False
        if cmd == "/help":
            table = Table(show_header=False, box=None, padding=(0, 2))
            for name, desc in COMMANDS.items():
                table.add_row(Text(name, style="cyan"), desc)
            self.console.print(table)
        elif cmd == "/reset":
            await self.runner.reset()
            self.turns = self.tokens_in = self.tokens_out = 0
            self.console.print(Text("  new session", style="green"))
        elif cmd == "/retry":
            if self.last_prompt:
                await self._turn(self.last_prompt)
            else:
                self.console.print("  nothing to retry")
        elif cmd == "/view":
            if arg in VIEWS:
                self.view = arg
            else:
                self.console.print(f"  view is '{self.view}'; choose one of: {', '.join(VIEWS)}")
        elif cmd == "/effort":
            from maf_labs_host.manifest import REASONING_EFFORTS

            if arg in (*REASONING_EFFORTS, "default"):
                try:
                    await self.runner.set_effort(None if arg == "default" else arg)
                    self.console.print(Text(f"  effort: {self.runner.info.get('effort')}", style="green"))
                except (NotImplementedError, RuntimeError) as e:
                    self.console.print(Text(f"  {e}", style="yellow"))
            else:
                self.console.print(
                    f"  effort is '{self.runner.info.get('effort', 'default')}'; "
                    f"choose one of: {', '.join(REASONING_EFFORTS)}, default"
                )
        elif cmd == "/info":
            print_info(self.console, self.runner.info)
        elif cmd == "/system":
            print_instructions(self.console, self.runner.info)
        elif cmd == "/trace":
            self.console.print(f"  {self.runner.info.get('trace', '(not recording — started with --no-trace)')}")
        elif cmd == "/clear":
            self.console.clear()
        else:
            self.console.print(Text(f"  unknown command {cmd} — /help", style="yellow"))
        return True

    async def run(self) -> None:
        print_info(self.console, self.runner.info)
        self.console.print(Text("  /help for commands", style="dim"))
        self.console.print()
        while True:
            text = await self._read()
            if text is None:
                return
            if not text.strip():
                continue
            stripped = text.strip()
            if stripped.lower() in BARE_COMMANDS:
                stripped = "/" + stripped.lower()
            if stripped.startswith("/"):
                if not await self._command(stripped):
                    return
                continue
            await self._turn(text)
            self.console.print()
