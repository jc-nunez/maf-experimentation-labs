"""Resolve ``project/component`` targets and create the right runner for each runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from maf_labs_host import Project, Workspace, discover_projects, find_workspace, load_project
from maf_labs_host.manifest import MANIFEST
from maf_labs_host.runner import RecordingRunner, Runner, create_runner
from maf_labs_host.workspace import load_env


class TargetError(RuntimeError):
    pass


@dataclass
class Target:
    workspace: Workspace
    project: Project
    kind: str  # agents | workflows | tools
    name: str
    runtime: str

    @property
    def label(self) -> str:
        return f"{self.project.name}/{self.name}"


def workspace(path: Path | None = None) -> Workspace:
    return find_workspace(path)


def projects(ws: Workspace) -> list[Project]:
    if not ws.projects_dir.is_dir():
        return []
    return discover_projects(ws.projects_dir)


def project(ws: Workspace, name: str) -> Project:
    path = ws.projects_dir / name
    if not (path / MANIFEST).is_file():
        known = ", ".join(p.name for p in projects(ws)) or "none"
        raise TargetError(f"no project '{name}' (known: {known})")
    return load_project(path)


def _cwd_project(ws: Workspace) -> Project | None:
    here = Path.cwd().resolve()
    for directory in [here, *here.parents]:
        if directory == ws.root:
            return None
        if (directory / MANIFEST).is_file():
            return load_project(directory)
    return None


def resolve(ws: Workspace, ref: str | None, kinds: tuple[str, ...] = ("agents", "workflows")) -> Target:
    """``project/component``, ``project`` (its default target), or ``component`` (cwd project or unique)."""
    proj: Project | None = None
    name: str | None = None
    if ref and "/" in ref:
        pname, name = ref.split("/", 1)
        proj = project(ws, pname)
    elif ref and (ws.projects_dir / ref / MANIFEST).is_file():
        proj = project(ws, ref)
    elif ref:
        name = ref
        proj = _cwd_project(ws)
        if proj is None:
            matches = [p for p in projects(ws) for k in kinds for s in getattr(p.components, k) if s.name == ref]
            if not matches:
                raise TargetError(f"no component named '{ref}' in any project")
            if len(matches) > 1:
                raise TargetError(f"'{ref}' is ambiguous: " + ", ".join(f"{p.name}/{ref}" for p in matches))
            proj = matches[0]
    else:
        proj = _cwd_project(ws)
        if proj is None:
            raise TargetError("give a target: mafx run <project>/<agent-or-workflow>")

    if name is None:
        name = proj.default_target()
    try:
        kind, spec = proj.find(name)
    except KeyError as e:
        raise TargetError(str(e)) from e
    if kind not in kinds:
        raise TargetError(f"'{proj.name}/{name}' is a {kind[:-1]}, expected one of: {', '.join(kinds)}")
    return Target(ws, proj, kind, name, spec.runtime)


def make_runner(
    target: Target,
    *,
    provider: str | None,
    model: str | None,
    record: bool,
    mode: str,
    build: bool = True,
    effort: str | None = None,
) -> Runner:
    load_env(target.workspace, target.project.root)
    if target.runtime == "dotnet":
        from .dotnet import DotnetRunner

        _, spec = target.project.find(target.name)
        # .NET hosts get the manifest's reasoning_effort as a flag unless --effort overrides it.
        runner: Runner = DotnetRunner(
            target,
            spec,
            provider=provider,
            model=model,
            build=build,
            effort=effort or getattr(spec, "reasoning_effort", None),
        )
    else:
        runner = create_runner(
            target.project,
            target.name,
            provider=provider,
            model=model,
            workspace_root=target.workspace.root,
            default_provider=target.workspace.default("provider"),
            reasoning_effort=effort,
        )
    if record:
        runner = RecordingRunner(runner, target.workspace.runs_dir, mode)
    return runner
