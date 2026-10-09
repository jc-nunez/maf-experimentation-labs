"""Workspace discovery: find the repo root (``maf-labs.yaml``) and load settings."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

MARKER = "maf-labs.yaml"


class WorkspaceNotFound(RuntimeError):
    pass


@dataclass
class Workspace:
    root: Path
    config: dict[str, Any] = field(default_factory=dict)

    def path(self, key: str, default: str) -> Path:
        return self.root / self.config.get("paths", {}).get(key, default)

    @property
    def projects_dir(self) -> Path:
        return self.path("projects", "projects")

    @property
    def shared_tools_dir(self) -> Path:
        return self.path("shared_tools", "tools")

    @property
    def runs_dir(self) -> Path:
        return self.path("runs", ".mafx/runs")

    @property
    def sessions_dir(self) -> Path:
        return self.path("sessions", ".mafx/sessions")

    def default(self, key: str, fallback: Any = None) -> Any:
        return self.config.get("defaults", {}).get(key, fallback)


def find_workspace(start: Path | str | None = None) -> Workspace:
    """Locate the workspace: ``MAFX_HOME`` first, then walk up from ``start`` (or cwd)."""
    if home := os.environ.get("MAFX_HOME"):
        candidates = [Path(home).expanduser().resolve()]
    else:
        here = Path(start or Path.cwd()).resolve()
        if here.is_file():
            here = here.parent
        candidates = [here, *here.parents]
    for directory in candidates:
        marker = directory / MARKER
        if marker.is_file():
            config = yaml.safe_load(marker.read_text()) or {}
            return Workspace(root=directory, config=config)
    raise WorkspaceNotFound(f"No {MARKER} found (searched from {candidates[0]}). Run inside the repo or set MAFX_HOME.")


def load_env(workspace: Workspace, project_dir: Path | None = None) -> None:
    """Load ``.env`` files: workspace root first, then the project (project values win)."""
    from dotenv import load_dotenv

    load_dotenv(workspace.root / ".env", override=False)
    if project_dir is not None:
        load_dotenv(project_dir / ".env", override=True)
