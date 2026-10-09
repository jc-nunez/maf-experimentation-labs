"""Interactive session: agentic-CLI style input box, streaming trajectory, slash commands."""

from __future__ import annotations

import asyncio
import contextlib
import signal
from pathlib import Path
from typing import Any

from maf_labs_host.runner import Runner
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.table import Table
from rich.text import Text

from .render import VIEWS, Renderer, print_info, print_instructions

COMMANDS = {
    "/help": "show this help",
    "/reset": "start a new session (clears history)",
    "/retry": "re-run the last prompt",
    "/view": "full | normal | quiet — how much of the trajectory to show",
    "/info": "target, provider, model, tools, trace file",
    "/system": "show the agent's instructions",
    "/trace": "print the path of this run's trace.jsonl",
    "/clear": "clear the screen",
    "/exit": "quit (also Ctrl+D)",
}

STYLE = Style.from_dict(
    {
        "prompt": "ansicyan bold",
        "frame": "ansibrightblack",
        "bottom-toolbar": "noreverse ansibrightblack",
    }
)


def _bindings() -> KeyBindings:
    kb = KeyBindings()

    @kb.add("enter")
    def _submit(event: Any) -> None:
        buf = event.current_buffer
        if buf.complete_state and buf.complete_state.current_completion:
            buf.apply_completion(buf.complete_state.current_completion)
            return
        buf.validate_and_handle()

    @kb.add("escape", "enter")  # Alt+Enter
    @kb.add("c-j")  # Ctrl+J (and Shift+Enter in many terminals)
    def _newline(event: Any) -> None:
        event.current_buffer.insert_text("\n")

    return kb


class Session:
    def __init__(self, runner: Runner, console: Console, view: str, history_dir: Path) -> None:
        self.runner = runner
        self.console = console
        self.view = view
        self.last_prompt: str | None = None
        self.turns = 0
        self.tokens_in = 0
        self.tokens_out = 0
        history_dir.mkdir(parents=True, exist_ok=True)
        safe = runner.target.replace("/", "__")
        self.prompt = PromptSession(
            history=FileHistory(str(history_dir / f"{safe}.history")),
            completer=WordCompleter(list(COMMANDS), sentence=True),
            complete_while_typing=True,
            multiline=True,
            key_bindings=_bindings(),
            style=STYLE,
            bottom_toolbar=self._toolbar,
            prompt_continuation=lambda width, line, soft: HTML("<frame>│ </frame>"),
        )

    def _toolbar(self) -> HTML:
        info = self.runner.info
        return HTML(
            f" <b>{info.get('target')}</b> · {info.get('provider', '?')} · {info.get('model', '?')}"
            f" · turns {self.turns} · in {self.tokens_in:,} / out {self.tokens_out:,} tok · view {self.view}"
            "    <i>⏎ send · Alt+⏎/Ctrl+J newline · / commands · Ctrl+C interrupt · Ctrl+D exit</i>"
        )

    async def _read(self) -> str | None:
        self.console.print(Text("╭" + "─" * (self.console.width - 2) + "╮", style="bright_black"))
        try:
            text = await self.prompt.prompt_async(HTML("<frame>│</frame> <prompt>›</prompt> "))
        except EOFError:
            return None
        except KeyboardInterrupt:
            return ""
        finally:
            self.console.print(Text("╰" + "─" * (self.console.width - 2) + "╯", style="bright_black"))
        return text

    async def _turn(self, text: str) -> None:
        self.last_prompt = text
        renderer = Renderer(self.console, view=self.view)
        self.console.print()

        async def consume() -> None:
            async for e in self.runner.turn(text):
                renderer.handle(e)
                if e["type"] == "turn_completed":
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
        self.console.print()

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
        while True:
            text = await self._read()
            if text is None:
                return
            if not text.strip():
                continue
            if text.strip().startswith("/"):
                if not await self._command(text):
                    return
                continue
            await self._turn(text)
