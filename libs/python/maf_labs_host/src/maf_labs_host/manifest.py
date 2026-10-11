"""Project manifest (``project.yaml``) model and loader."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

Runtime = Literal["python", "declarative", "dotnet"]
Kind = Literal["agents", "tools", "workflows"]
# Reasoning effort values across providers. SGLang (Qwen3.8) accepts none, low, medium and xhigh (default).
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]
REASONING_EFFORTS: tuple[str, ...] = ("none", "minimal", "low", "medium", "high", "xhigh")
MANIFEST = "project.yaml"


class _Component(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    runtime: Runtime = "python"
    entry: str | None = Field(None, description="python: 'module:attribute'")
    file: str | None = Field(None, description="declarative YAML file, or a .NET single-file app (.cs)")
    project: str | None = Field(None, description="dotnet: path to the .csproj")

    @model_validator(mode="after")
    def _check_runtime_fields(self) -> _Component:
        if self.runtime == "python" and not self.entry and type(self) is not ToolSpec:
            raise ValueError(f"{self.name}: python components need 'entry: module:attribute'")
        if self.runtime == "declarative" and not self.file:
            raise ValueError(f"{self.name}: declarative components need 'file'")
        if self.runtime == "dotnet" and not (self.project or self.file):
            raise ValueError(f"{self.name}: dotnet components need 'project' (.csproj) or 'file' (.cs)")
        return self


class AgentSpec(_Component):
    tools: list[str] = Field(default_factory=list, description="tool names from this manifest to attach")
    reasoning_effort: ReasoningEffort | None = Field(
        None, description="default reasoning effort for this agent (overridden by --effort)"
    )


class WorkflowSpec(_Component):
    pass


class ToolSpec(_Component):
    kind: Literal["function", "mcp", "openapi", "ref"] = "function"
    # mcp
    transport: Literal["stdio", "http", "websocket"] | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    # openapi
    spec: str | None = None
    # ref to a shared tool package under tools/
    ref: str | None = None

    @model_validator(mode="after")
    def _check_kind(self) -> ToolSpec:
        if self.kind == "function" and self.runtime == "python" and not self.entry:
            raise ValueError(f"{self.name}: function tools need 'entry: module:attribute'")
        if self.kind == "mcp":
            if self.transport is None:
                self.transport = "http" if self.url else "stdio"
            if self.transport == "stdio" and not self.command:
                raise ValueError(f"{self.name}: stdio MCP tools need 'command'")
            if self.transport in ("http", "websocket") and not self.url:
                raise ValueError(f"{self.name}: {self.transport} MCP tools need 'url'")
        if self.kind == "openapi" and not self.spec:
            raise ValueError(f"{self.name}: openapi tools need 'spec'")
        if self.kind == "ref" and not self.ref:
            raise ValueError(f"{self.name}: ref tools need 'ref'")
        return self


class Components(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agents: list[AgentSpec] = Field(default_factory=list)
    tools: list[ToolSpec] = Field(default_factory=list)
    workflows: list[WorkflowSpec] = Field(default_factory=list)


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    status: Literal["incubating", "active", "archived"] = "incubating"
    tags: list[str] = Field(default_factory=list)
    python_package: str | None = Field(None, description="import name of the project's python package")
    components: Components = Field(default_factory=Components)

    # Set by the loader, not part of the YAML.
    root: Path = Field(default=Path("."), exclude=True)

    def find(self, name: str) -> tuple[str, AgentSpec | ToolSpec | WorkflowSpec]:
        for kind in ("agents", "workflows", "tools"):
            for spec in getattr(self.components, kind):
                if spec.name == name:
                    return kind, spec
        raise KeyError(f"'{name}' is not defined in {self.name}/{MANIFEST}")

    def tool(self, name: str) -> ToolSpec:
        for spec in self.components.tools:
            if spec.name == name:
                return spec
        raise KeyError(f"tool '{name}' is not defined in {self.name}/{MANIFEST}")

    def default_target(self) -> str:
        for kind in ("agents", "workflows"):
            specs = getattr(self.components, kind)
            if specs:
                return specs[0].name
        raise KeyError(f"{self.name} has no agents or workflows")


def load_project(path: Path | str) -> Project:
    """Load a project from its directory or its ``project.yaml``."""
    path = Path(path)
    manifest = path if path.name == MANIFEST else path / MANIFEST
    data = yaml.safe_load(manifest.read_text()) or {}
    project = Project.model_validate(data)
    project.root = manifest.parent.resolve()
    return project


def find_project_dir(start: Path | str) -> Path:
    """Walk up from ``start`` until a directory with ``project.yaml`` is found."""
    here = Path(start).resolve()
    if here.is_file():
        here = here.parent
    for directory in [here, *here.parents]:
        if (directory / MANIFEST).is_file():
            return directory
    raise FileNotFoundError(f"No {MANIFEST} found above {start}")


def discover_projects(projects_dir: Path) -> list[Project]:
    projects = []
    for manifest in sorted(projects_dir.glob(f"*/{MANIFEST}")):
        projects.append(load_project(manifest))
    return projects
