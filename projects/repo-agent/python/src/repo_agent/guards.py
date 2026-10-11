"""Guards shared by every repo-agent tool: path guard, command allowlist and action log.

The guards live in code, not in prompts: a tool cannot reach a path outside its workspace or run a command that is
not on the allowlist, whatever the model asks for.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_ENV = "REPO_AGENT_ROOT"
PROJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class GuardError(PermissionError):
    """A path or command was refused by a guard."""


def workspaces_root() -> Path:
    """``~/workspaces`` unless ``REPO_AGENT_ROOT`` overrides it."""
    return Path(os.environ.get(ROOT_ENV) or Path.home() / "workspaces").expanduser().resolve()


def workspace_dir(project: str, root: Path | None = None) -> Path:
    """``<root>/<project>``; the project name is a plain kebab-case folder name, never a path."""
    if not PROJECT_NAME.match(project):
        raise GuardError(f"invalid project name '{project}' (lower-case letters, digits and '-')")
    return (root or workspaces_root()) / project


class PathGuard:
    """Allows only paths inside one workspace folder (after resolving symlinks and '..')."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def check(self, path: str | Path) -> Path:
        resolved = Path(path).expanduser().resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise GuardError(f"path '{path}' is outside the workspace {self.root}")
        return resolved


# Placeholders in allowlist patterns. Anything else in a pattern is a literal argv token.
URL = "{url}"
PATH = "{path}"
FIELDS = "{fields}"
_FIELDS = re.compile(r"^[A-Za-z]+(,[A-Za-z]+)*$")


@dataclass(frozen=True)
class Allowlist:
    """Exact argv patterns. A command runs only if it matches one pattern token by token.

    ``{url}`` accepts a URL with one of ``url_schemes``; ``{path}`` accepts a path (checked by the PathGuard);
    ``{fields}`` accepts a comma-separated list of field names. No pattern contains a force flag.
    """

    patterns: tuple[tuple[str, ...], ...]
    url_schemes: tuple[str, ...] = ("https",)

    def match(self, argv: list[str]) -> list[str]:
        """Return the argv tokens that are paths (for the PathGuard), or raise GuardError."""
        for pattern in self.patterns:
            paths = self._match(pattern, argv)
            if paths is not None:
                return paths
        raise GuardError(f"command not on the allowlist: {' '.join(argv)}")

    def _match(self, pattern: tuple[str, ...], argv: list[str]) -> list[str] | None:
        if len(pattern) != len(argv):
            return None
        paths: list[str] = []
        for expected, token in zip(pattern, argv, strict=True):
            if expected == URL:
                if not any(token.startswith(f"{scheme}://") for scheme in self.url_schemes):
                    return None
            elif expected == PATH:
                if token.startswith("-"):
                    return None
                paths.append(token)
            elif expected == FIELDS:
                if not _FIELDS.match(token):
                    return None
            elif expected != token:
                return None
        return paths


SLICE1_PATTERNS: tuple[tuple[str, ...], ...] = (
    ("git", "clone", URL, PATH),
    ("git", "status", "--porcelain=v2", "--branch"),
    ("git", "worktree", "list", "--porcelain"),
    ("git", "log", "-1", "--format=%h %cs %s"),
    ("gh", "pr", "list", "--state", "open", "--json", FIELDS),
)


def slice1_allowlist(url_schemes: tuple[str, ...] = ("https",)) -> Allowlist:
    return Allowlist(SLICE1_PATTERNS, url_schemes)


class ActionLog:
    """Append-only JSONL log of write actions: time, caller, tool, argv, result."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, *, caller: str, tool: str, argv: list[list[str]], result: str) -> dict[str, Any]:
        entry = {
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "caller": caller,
            "tool": tool,
            "argv": argv,
            "result": result,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    def entries(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
