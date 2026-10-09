"""Build agents, tools and workflows from a project manifest (in-process runtimes)."""

from __future__ import annotations

import importlib
import inspect
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .manifest import AgentSpec, Project, ToolSpec, WorkflowSpec
from .providers import ProviderInfo


class ComponentError(RuntimeError):
    pass


@dataclass
class HostContext:
    """Everything a component factory may need. Passed to factories that accept a ``context`` arg."""

    project: Project
    client: Any
    provider: ProviderInfo
    workspace_root: Path | None = None
    settings: dict[str, Any] = field(default_factory=dict)

    def tools(self, *names: str) -> list[Any]:
        """Build tools declared in the manifest by name (for use inside python factories)."""
        return [build_tool(self.project.tool(n), self) for n in names]


def _ensure_importable(project: Project) -> None:
    for src in (project.root / "python" / "src", project.root / "src"):
        if src.is_dir() and str(src) not in sys.path:
            sys.path.insert(0, str(src))


def import_entry(entry: str, project: Project) -> Any:
    """Import ``package.module:attribute``."""
    if ":" not in entry:
        raise ComponentError(f"entry '{entry}' must look like 'package.module:attribute'")
    _ensure_importable(project)
    module_name, attr = entry.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        raise ComponentError(f"cannot import '{module_name}' for {project.name}: {e}") from e
    try:
        return getattr(module, attr)
    except AttributeError as e:
        raise ComponentError(f"'{module_name}' has no attribute '{attr}'") from e


def _call_factory(factory: Any, ctx: HostContext) -> Any:
    """Call ``factory(client)`` or ``factory(client, context=ctx)`` depending on its signature."""
    params = inspect.signature(factory).parameters
    kwargs = {"context": ctx} if "context" in params else {}
    if "client" in params or (params and next(iter(params)) != "context"):
        return factory(ctx.client, **kwargs)
    return factory(**kwargs)


def _quiet_stdout() -> Any:
    """The declarative package's powerfx loader prints banners to stdout on first use. stdout is reserved for
    answers (-p) and the JSONL protocol (--stdio), so swallow anything printed while building."""
    import contextlib
    import io

    return contextlib.redirect_stdout(io.StringIO())


def _declarative() -> Any:
    with _quiet_stdout():
        from agent_framework import declarative
    return declarative


# --------------------------------------------------------------------------------------------- tools


def build_tool(spec: ToolSpec, ctx: HostContext | None = None, project: Project | None = None) -> Any:
    project = project or (ctx.project if ctx else None)
    if project is None:
        raise ComponentError("build_tool needs a project or context")

    if spec.runtime != "python" and spec.kind == "function":
        raise ComponentError(f"tool '{spec.name}' is a {spec.runtime} tool; only the {spec.runtime} host can load it")

    if spec.kind == "function":
        obj = import_entry(spec.entry or "", project)
        from agent_framework import FunctionTool, tool

        return obj if isinstance(obj, FunctionTool) else tool(obj, name=spec.name)

    if spec.kind == "mcp":
        from agent_framework import MCPStdioTool, MCPStreamableHTTPTool, MCPWebsocketTool

        if spec.transport == "stdio":
            parts = shlex.split(spec.command or "")
            return MCPStdioTool(
                name=spec.name, command=parts[0], args=[*parts[1:], *spec.args], description=spec.description
            )
        if spec.transport == "websocket":
            return MCPWebsocketTool(name=spec.name, url=spec.url, description=spec.description)
        return MCPStreamableHTTPTool(name=spec.name, url=spec.url, description=spec.description)

    if spec.kind == "ref":
        ref_dir = Path(spec.ref or "")
        if not ref_dir.is_absolute():
            from .workspace import find_workspace

            ref_dir = find_workspace(project.root).root / ref_dir
        tool_file = ref_dir / "tool.yaml"
        if not tool_file.is_file():
            raise ComponentError(f"shared tool '{spec.ref}' has no tool.yaml")
        shared = ToolSpec.model_validate({"name": spec.name, **(yaml.safe_load(tool_file.read_text()) or {})})
        shared_project = Project(name=f"shared:{ref_dir.name}")
        shared_project.root = ref_dir
        return build_tool(shared, project=shared_project)

    raise ComponentError(f"tool kind '{spec.kind}' is not supported by the python host yet")


# -------------------------------------------------------------------------------------------- agents


def build_agent(spec: AgentSpec, ctx: HostContext) -> Any:
    if spec.runtime == "python":
        factory = import_entry(spec.entry or "", ctx.project)
        agent = _call_factory(factory, ctx) if callable(factory) and not hasattr(factory, "run") else factory
    elif spec.runtime == "declarative":
        path = ctx.project.root / (spec.file or "")
        with _quiet_stdout():
            agent = _declarative().AgentFactory(client=ctx.client).create_agent_from_yaml_path(str(path))
    else:
        raise ComponentError(f"agent '{spec.name}' runs on {spec.runtime}; use mafx or the {spec.runtime} host")

    # Apply provider defaults (e.g. store=false for self-hosted Responses servers) unless the agent set them.
    options = getattr(agent, "default_options", None)
    if isinstance(options, dict):
        for key, value in ctx.provider.default_options.items():
            options.setdefault(key, value)
    return agent


def agent_tools(spec: AgentSpec, ctx: HostContext) -> list[Any]:
    """Tools the manifest attaches to an agent (in addition to those the factory set)."""
    return [build_tool(ctx.project.tool(name), ctx) for name in spec.tools]


# ----------------------------------------------------------------------------------------- workflows


def build_workflow(spec: WorkflowSpec, ctx: HostContext) -> Any:
    if spec.runtime == "python":
        factory = import_entry(spec.entry or "", ctx.project)
        return _call_factory(factory, ctx) if callable(factory) and not hasattr(factory, "run") else factory
    if spec.runtime == "declarative":
        declarative = _declarative()
        path = ctx.project.root / (spec.file or "")
        with _quiet_stdout():
            factory = declarative.WorkflowFactory(agent_factory=declarative.AgentFactory(client=ctx.client))
            return factory.create_workflow_from_yaml_path(str(path))
    raise ComponentError(f"workflow '{spec.name}' runs on {spec.runtime}; use mafx or the {spec.runtime} host")
