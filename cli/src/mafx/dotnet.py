"""Run .NET hosts (project or single-file app) over the JSONL stdio protocol."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from collections.abc import AsyncIterator
from typing import Any

from maf_labs_host import events as ev
from maf_labs_host.runner import Runner


class DotnetUnavailable(RuntimeError):
    pass


def dotnet_command(project_root, spec, extra: list[str], build: bool = True) -> list[str]:
    exe = shutil.which("dotnet")
    if exe is None:
        raise DotnetUnavailable("the .NET SDK (dotnet) is not on PATH; install .NET 10 to run dotnet components")
    if spec.project:
        cmd = [exe, "run", "--project", str(project_root / spec.project)]
    else:
        cmd = [exe, "run", str(project_root / spec.file)]
    if not build:
        cmd.append("--no-build")
    return [*cmd, "--", *extra]


class DotnetRunner(Runner):
    """Starts the .NET host once with ``--stdio`` and exchanges JSON Lines, keeping the session alive."""

    kind = "agent"

    def __init__(
        self, target, spec, *, provider: str | None, model: str | None, build: bool = True, effort: str | None = None
    ) -> None:
        self.target = target.label
        self.kind = "workflow" if target.kind == "workflows" else "agent"
        args = ["--stdio", target.name]
        if provider:
            args += ["--provider", provider]
        elif default := target.workspace.default("provider"):
            args += ["--provider", os.environ.get("MAF_PROVIDER", default)]
        if model:
            args += ["--model", model]
        if effort:
            args += ["--effort", effort]
        self.cmd = dotnet_command(target.project.root, spec, args, build=build)
        self.cwd = target.project.root
        self.proc: asyncio.subprocess.Process | None = None
        self.info = {"target": self.target, "kind": self.kind, "runtime": "dotnet", "command": " ".join(self.cmd)}
        self._stderr_task: asyncio.Task | None = None
        self.stderr_lines: list[str] = []

    async def _drain_stderr(self) -> None:
        assert self.proc and self.proc.stderr
        async for line in self.proc.stderr:
            self.stderr_lines.append(line.decode(errors="replace").rstrip())
            del self.stderr_lines[:-200]

    async def _read(self) -> dict[str, Any] | None:
        assert self.proc and self.proc.stdout
        while True:
            line = await self.proc.stdout.readline()
            if not line:
                return None
            text = line.decode(errors="replace").strip()
            if not text:
                continue
            try:
                return json.loads(text)
            except ValueError:
                # dotnet build output or stray Console.WriteLine — keep it out of the event stream
                self.stderr_lines.append(text)

    async def _send(self, msg: dict[str, Any]) -> None:
        assert self.proc and self.proc.stdin
        self.proc.stdin.write((json.dumps(msg) + "\n").encode())
        await self.proc.stdin.drain()

    async def start(self) -> None:
        self.proc = await asyncio.create_subprocess_exec(
            *self.cmd,
            cwd=self.cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=16 * 1024 * 1024,
        )
        self._stderr_task = asyncio.create_task(self._drain_stderr())
        ready = await self._read()
        if not ready or ready.get("type") != "ready":
            tail = "\n".join(self.stderr_lines[-20:])
            raise RuntimeError(f".NET host did not start ({' '.join(self.cmd)}):\n{tail}")
        self.info.update(ready.get("info") or {})
        self.info.update(target=self.target, runtime="dotnet")

    async def reset(self) -> None:
        await self._send({"type": "reset"})
        while (msg := await self._read()) is not None and msg.get("type") != "reset_done":
            pass

    async def set_effort(self, effort: str | None) -> None:
        await self._send({"type": "set_effort", "effort": effort})
        while (msg := await self._read()) is not None:
            if msg.get("type") == "effort_set":
                self.info["effort"] = msg.get("effort")
                return
            if msg.get("type") == "error":
                raise RuntimeError(msg.get("message"))

    async def close(self) -> None:
        if self.proc and self.proc.returncode is None:
            try:
                await self._send({"type": "exit"})
                await asyncio.wait_for(self.proc.wait(), timeout=5)
            except (Exception, asyncio.TimeoutError):  # noqa: BLE001
                self.proc.kill()
        if self._stderr_task:
            self._stderr_task.cancel()

    async def turn(self, text: str) -> AsyncIterator[dict[str, Any]]:
        await self._send({"type": "user", "text": text})
        while True:
            msg = await self._read()
            if msg is None:
                tail = "\n".join(self.stderr_lines[-20:])
                yield ev.event(ev.ERROR, message=f".NET host exited unexpectedly\n{tail}")
                yield ev.event(
                    ev.TURN_COMPLETED,
                    ok=False,
                    text="",
                    duration_s=0,
                    input_tokens=0,
                    output_tokens=0,
                    model_calls=0,
                    tool_calls=0,
                )
                return
            yield msg
            if msg.get("type") == ev.TURN_COMPLETED:
                return
