"""Standalone host entry point — the argument contract every host (Python and .NET) implements.

    <host> [target] -p "prompt"        run once and exit (answer → stdout, trajectory → stderr)
    <host> [target]                    simple interactive loop (use `mafx run` for the rich UI)
    <host> [target] --stdio            JSON Lines protocol on stdin/stdout (used by mafx)
    <host> --list                      list the project's components

Common options: --output text|json|jsonl, --provider, --model, --quiet. See docs/host-protocol.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from . import events as ev
from .manifest import Project, find_project_dir, load_project
from .runner import RecordingRunner, Runner, create_runner
from .workspace import WorkspaceNotFound, find_workspace, load_env


def build_parser(prog: str | None = None) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=prog, description="Run a project's agents and workflows.")
    p.add_argument("target", nargs="?", help="agent or workflow name (default: first agent)")
    p.add_argument("-p", "--prompt", help="run once with this prompt and exit ('-' reads stdin)")
    p.add_argument("--output", choices=["text", "json", "jsonl"], default="text")
    p.add_argument("--provider", help="sglang | openai | azure-openai | foundry | mock")
    p.add_argument("--model", help="override the provider's model")
    p.add_argument("--stdio", action="store_true", help="speak the JSONL host protocol on stdin/stdout")
    p.add_argument("--list", action="store_true", help="list components and exit")
    p.add_argument("--quiet", action="store_true", help="text mode: do not print the trajectory to stderr")
    p.add_argument("--no-trace", action="store_true", help="do not write .mafx/runs/<id>/trace.jsonl")
    return p


def _plain(event: dict[str, Any], out: Any) -> None:
    """Minimal plain-text trajectory renderer (stderr). mafx provides the rich version."""
    t = event["type"]
    if t == ev.REASONING:
        out.write(event["text"])
    elif t == ev.TOOL_CALL:
        out.write(f"\n⏺ {event['name']}({json.dumps(event['arguments'])})  [{event['call_id']}]\n")
    elif t == ev.TOOL_RESULT:
        body = event["error"] or json.dumps(event["result"], default=str)
        out.write(f"  ⎿ {body}\n")
    elif t == ev.EXECUTOR_STARTED:
        out.write(f"\n▶ {event['executor_id']}\n")
    elif t == ev.REQUEST_INFO:
        out.write(f"\n? input requested ({event.get('request_id')}): {event.get('data')}\n")
    elif t in (ev.ERROR, ev.WARNING):
        out.write(f"\n{t}: {event.get('message')}\n")
    elif t == ev.TURN_COMPLETED:
        out.write(
            f"\n── {event['model_calls']} model calls · {event['tool_calls']} tool calls · "
            f"in {event['input_tokens']} / out {event['output_tokens']} tok · {event['duration_s']}s ──\n"
        )
    out.flush()


async def _run_once(runner: Runner, prompt: str, output: str, quiet: bool) -> int:
    collected: list[dict[str, Any]] = []
    async for e in runner.turn(prompt):
        collected.append(e)
        if output == "jsonl":
            print(json.dumps(e, default=str), flush=True)
        elif output == "text" and not quiet:
            _plain(e, sys.stderr)
    done = collected[-1] if collected else {}
    if output == "text":
        print(done.get("text", "").strip())
    elif output == "json":
        print(json.dumps({"info": runner.info, "result": done, "events": collected}, default=str, indent=2))
    return 0 if done.get("ok", False) else 1


async def _interactive(runner: Runner) -> int:
    print(f"{runner.target} — type /exit to quit, /reset for a new session", file=sys.stderr)
    while True:
        try:
            text = await asyncio.to_thread(input, "› ")
        except (EOFError, KeyboardInterrupt):
            return 0
        if text.strip() in ("/exit", "/quit"):
            return 0
        if text.strip() == "/reset":
            await runner.reset()
            continue
        if not text.strip():
            continue
        async for e in runner.turn(text):
            if e["type"] == ev.TEXT:
                sys.stdout.write(e["text"])
                sys.stdout.flush()
            else:
                _plain(e, sys.stderr)
        print()


async def serve_stdio(runner: Runner) -> int:
    """JSONL protocol. In: {"type": "user", "text"} | {"type": "reset"} | {"type": "exit"}.
    Out: {"type": "ready", "info"} then trajectory events per turn."""

    def send(obj: dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(obj, default=str) + "\n")
        sys.stdout.flush()

    send(ev.event("ready", info=runner.info))
    while True:
        line = await asyncio.to_thread(sys.stdin.readline)
        if not line:
            return 0
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            send(ev.event(ev.ERROR, message=f"invalid JSON: {line[:100]}"))
            continue
        mtype = msg.get("type")
        if mtype == "exit":
            return 0
        if mtype == "reset":
            await runner.reset()
            send(ev.event("reset_done"))
        elif mtype == "user":
            async for e in runner.turn(msg.get("text", "")):
                send(e)
        else:
            send(ev.event(ev.ERROR, message=f"unknown message type: {mtype}"))


def _list(project: Project) -> int:
    for kind in ("agents", "tools", "workflows"):
        for spec in getattr(project.components, kind):
            print(f"{kind[:-1]:9} {spec.name:24} {spec.runtime:12} {spec.description or ''}")
    return 0


async def _amain(project: Project, args: argparse.Namespace) -> int:
    try:
        workspace = find_workspace(project.root)
    except WorkspaceNotFound:
        workspace = None
    load_env(workspace, project.root) if workspace else None
    default_provider = workspace.default("provider") if workspace else None

    runner: Runner = create_runner(
        project,
        args.target,
        provider=args.provider,
        model=args.model,
        workspace_root=workspace.root if workspace else None,
        default_provider=default_provider,
    )
    if workspace and not args.no_trace:
        mode = "stdio" if args.stdio else ("once" if args.prompt is not None else "interactive")
        runner = RecordingRunner(runner, workspace.runs_dir, mode)
    await runner.start()
    try:
        if args.stdio:
            return await serve_stdio(runner)
        if args.prompt is not None:
            prompt = sys.stdin.read() if args.prompt == "-" else args.prompt
            return await _run_once(runner, prompt, args.output, args.quiet)
        return await _interactive(runner)
    finally:
        await runner.close()


def run_project(anchor: str | Path, argv: list[str] | None = None) -> None:
    """Entry point for a project's ``__main__``: ``run_project(__file__)``."""
    project = load_project(find_project_dir(anchor))
    args = build_parser(prog=project.name).parse_args(argv)
    if args.list:
        raise SystemExit(_list(project))
    try:
        code = asyncio.run(_amain(project, args))
    except KeyboardInterrupt:
        code = 130
    except Exception as exc:  # noqa: BLE001 - one clean error line instead of a traceback
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        code = 2
    raise SystemExit(code)


def main() -> None:
    """``maf-host`` console script: run the project in the current directory."""
    run_project(Path.cwd())
