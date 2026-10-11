"""The only way repo-agent runs git or gh: allowlist check, path guard, then subprocess without a shell."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from repo_agent.guards import Allowlist, PathGuard

TIMEOUT_SECONDS = 300


@dataclass
class Result:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class Runner:
    """Runs allowlisted commands inside one workspace. Raises GuardError before anything is executed."""

    def __init__(self, guard: PathGuard, allowlist: Allowlist) -> None:
        self.guard = guard
        self.allowlist = allowlist

    def run(self, argv: list[str], cwd: Path) -> Result:
        for path in self.allowlist.match(argv):
            self.guard.check(cwd / path)
        workdir = self.guard.check(cwd)
        # Never prompt for credentials or open an editor: the caller is a tool, not a terminal.
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_EDITOR": "true", "GH_PROMPT_DISABLED": "1"}
        try:
            proc = subprocess.run(
                argv, cwd=workdir, env=env, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            return Result(argv, -1, "", str(e))
        return Result(argv, proc.returncode, proc.stdout, proc.stderr)
