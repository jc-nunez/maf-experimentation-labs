"""Templates for ``mafx new project|agent|tool|workflow``."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

RUNTIMES = ("python", "declarative", "dotnet")
KINDS = {"agent": "agents", "tool": "tools", "workflow": "workflows"}


class ScaffoldError(RuntimeError):
    pass


def snake(name: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()


def pascal(name: str) -> str:
    return "".join(part.capitalize() for part in re.split(r"[^0-9a-zA-Z]+", name) if part)


def kebab(name: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "-", name).strip("-").lower()


def _write(path: Path, content: str, created: list[Path]) -> None:
    if path.exists():
        raise ScaffoldError(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"))
    created.append(path)


# --------------------------------------------------------------------------------------------- manifest


def add_to_manifest(manifest: Path, kind: str, entry: dict) -> None:
    """Insert a component under ``components.<kind>`` while keeping comments and layout intact."""
    data = yaml.safe_load(manifest.read_text()) or {}
    existing = (data.get("components") or {}).get(kind) or []
    if any(c.get("name") == entry["name"] for c in existing):
        raise ScaffoldError(f"{kind[:-1]} '{entry['name']}' already exists in {manifest}")

    item = yaml.safe_dump([entry], sort_keys=False, default_flow_style=False).rstrip("\n")
    block = "\n".join("    " + line if line else line for line in item.splitlines())
    lines = manifest.read_text().splitlines()

    header = re.compile(rf"^  {kind}:\s*(\[\])?\s*$")
    for i, line in enumerate(lines):
        if header.match(line):
            lines[i] = f"  {kind}:"
            end = i + 1
            while end < len(lines) and (
                not lines[end].strip() or lines[end].startswith("   ") or lines[end].lstrip().startswith("#")
            ):
                end += 1
            while end > i + 1 and not lines[end - 1].strip():
                end -= 1
            lines[end:end] = ["", *block.splitlines()] if end > i + 1 else block.splitlines()
            if end + len(block.splitlines()) + 1 < len(lines) and lines[end + len(block.splitlines()) + 1].strip():
                lines.insert(end + len(block.splitlines()) + (1 if end > i + 1 else 0), "")
            break
    else:
        if not any(line.startswith("components:") for line in lines):
            lines += ["", "components:"]
        lines += [f"  {kind}:", *block.splitlines()]
    manifest.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------------------------- project

PROJECT_YAML = """
# Project manifest — the source of truth for mafx and the shared hosts. See docs/manifest.md.
name: {name}
description: {description}
status: incubating
tags: []
python_package: {package}

components:
  agents: []
  tools: []
  workflows: []
"""

PROJECT_README = """
# {name}

{description}

```bash
mafx show {name}                 # components
mafx run {name}/<agent> -p "hi"  # run once
mafx run {name}/<agent>          # interactive
mafx new agent {name} <agent-name> --runtime python|declarative|dotnet
```
"""

PY_PYPROJECT = """
[project]
name = "{name}"
version = "0.1.0"
description = "{description}"
requires-python = ">=3.10"
dependencies = ["maf-labs-host"]

[project.scripts]
{name} = "{package}.__main__:main"

[tool.uv.sources]
maf-labs-host = {{ workspace = true }}

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{package}"]
"""

PY_MAIN = '''
"""Run this project without mafx:  uv run python -m {package} [target] [-p "prompt"]."""

from maf_labs_host import run_project


def main() -> None:
    run_project(__file__)


if __name__ == "__main__":
    main()
'''

PY_TEST = '''
"""Offline smoke test: every agent/workflow in the manifest builds and runs on the mock provider."""

from pathlib import Path

import pytest
from maf_labs_host import create_runner, load_project
from maf_labs_host.events import collect

PROJECT = load_project(Path(__file__).resolve().parents[2])
TARGETS = [s.name for k in ("agents", "workflows") for s in getattr(PROJECT.components, k) if s.runtime != "dotnet"]


@pytest.mark.parametrize("target", TARGETS or [pytest.param(None, marks=pytest.mark.skip("no components yet"))])
async def test_runs_on_mock(target):
    runner = create_runner(PROJECT, target, provider="mock")
    await runner.start()
    events = await collect(runner.turn("hello"))
    assert events[-1]["type"] == "turn_completed" and events[-1]["ok"], events
    await runner.close()
'''

CSPROJ = """
<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <RootNamespace>{pascal}</RootNamespace>
  </PropertyGroup>

  <ItemGroup>
    <ProjectReference Include="{hosting}" />
  </ItemGroup>

</Project>
"""

PROGRAM_CS = """
using MafLabs.Hosting;

// Shared host: provider/model from .env, -p (run once), interactive, --stdio (used by mafx).
var host = MafLabsHost.Create(args);

// Register agents here, or add more single-file apps next to this project (mafx new agent ... --runtime dotnet).
// host.AddAgent("my-agent", instructions: "You are helpful.", tools: [AIFunctionFactory.Create(MyTools.DoThing)]);

return await host.RunAsync();
"""


def new_project(projects_dir: Path, name: str, description: str, runtimes: list[str], hosting_rel: str) -> list[Path]:
    name = kebab(name)
    root = projects_dir / name
    if root.exists():
        raise ScaffoldError(f"{root} already exists")
    package = snake(name)
    created: list[Path] = []
    _write(root / "project.yaml", PROJECT_YAML.format(name=name, description=description, package=package), created)
    _write(root / "README.md", PROJECT_README.format(name=name, description=description), created)
    if "python" in runtimes:
        py = root / "python"
        _write(py / "pyproject.toml", PY_PYPROJECT.format(name=name, description=description, package=package), created)
        pkg = py / "src" / package
        _write(pkg / "__init__.py", f'"""{name}: {description}"""\n', created)
        _write(pkg / "__main__.py", PY_MAIN.format(package=package), created)
        for sub in ("agents", "tools", "workflows"):
            _write(pkg / sub / "__init__.py", "", created)
        _write(py / "tests" / f"test_{package}.py", PY_TEST, created)
    if "declarative" in runtimes:
        for sub in ("agents", "workflows"):
            _write(root / "declarative" / sub / ".gitkeep", "", created)
    if "dotnet" in runtimes:
        # Project-based app in its own folder; single-file apps go to dotnet/apps/ (a .csproj would otherwise
        # glob them into its compilation).
        pas = pascal(name)
        _write(root / "dotnet" / pas / f"{pas}.csproj", CSPROJ.format(pascal=pas, hosting=hosting_rel), created)
        _write(root / "dotnet" / pas / "Program.cs", PROGRAM_CS, created)
    return created


# -------------------------------------------------------------------------------------------- components

PY_AGENT = '''
"""{name} agent."""

from agent_framework import Agent

INSTRUCTIONS = """You are {name}, a helpful assistant."""


def create_agent(client) -> Agent:
    # Tools listed under this agent in project.yaml are attached by the host at run time.
    # Use `def create_agent(client, context)` to build manifest tools here: context.tools("name").
    return Agent(client, INSTRUCTIONS, name="{name}")
'''

YAML_AGENT = """
# Declarative agent (kind: Prompt). The model/provider comes from the host.
kind: Prompt
name: {name}
description: {name} agent
instructions: |
  You are {name}, a helpful assistant.
"""

DOTNET_AGENT = """
#:project {hosting}
// .NET 10 single-file app: dotnet run {name}.cs -- -p "hello"
using MafLabs.Hosting;
using Microsoft.Extensions.AI;

var host = MafLabsHost.Create(args);

host.AddAgent("{name}", instructions: "You are {name}, a helpful assistant.", tools: []);

return await host.RunAsync();
"""

PY_TOOL = '''
"""{name} tool."""

from typing import Annotated

from agent_framework import tool
from pydantic import Field


@tool(name="{name}", description="Describe what {name} does — the model reads this.")
def {func}(value: Annotated[str, Field(description="Describe the argument")]) -> dict:
    return {{"echo": value}}
'''

PY_TOOL_TEST = """
from {package}.tools.{module} import {func}


async def test_{func}():
    result = await {func}.invoke(arguments={{"value": "x"}}, skip_parsing=True)
    assert result == {{"echo": "x"}}
"""

SHARED_TOOL_YAML = """
# Shared tool definition. Reference it from a project manifest with:
#   - {{ name: {name}, kind: ref, ref: tools/python/{name} }}
kind: function
runtime: python
entry: {package}.tool:{func}
description: {name} (shared)
"""

SHARED_TOOL_PYPROJECT = """
[project]
name = "{name}"
version = "0.1.0"
description = "Shared tool: {name}"
requires-python = ">=3.10"
dependencies = ["agent-framework-core>=1.21"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{package}"]
"""

PY_WORKFLOW = '''
"""{name} workflow."""

from agent_framework import Agent, WorkflowBuilder


def create_workflow(client):
    first = Agent(client, "You handle the first step of the request.", name="step1")
    second = Agent(client, "You refine the previous step's output.", name="step2")
    return (
        WorkflowBuilder(name="{name}", start_executor=first, output_from=[second],
                        intermediate_output_from="all_other")
        .add_edge(first, second)
        .build()
    )
'''

YAML_WORKFLOW = """
# Declarative workflow (kind: Workflow). Experimental upstream; "=..." PowerFx needs .NET + powerfx.
kind: Workflow
trigger:
  kind: OnConversationStart
  id: {snake}
  actions:
    - kind: SendActivity
      id: reply
      activity: "{name} received: {{System.LastMessage.Text}}"
"""


def new_component(
    project_root: Path,
    package: str | None,
    kind: str,
    name: str,
    runtime: str,
    *,
    tool_kind: str = "function",
    shared_tools_dir: Path | None = None,
    hosting_from_dotnet_dir: str = "../../../../libs/dotnet/MafLabs.Hosting/MafLabs.Hosting.csproj",
) -> tuple[list[Path], dict]:
    name = kebab(name)
    module = snake(name)
    created: list[Path] = []
    entry: dict = {"name": name, "runtime": runtime}
    pkg_dir = project_root / "python" / "src" / (package or "")

    def need_python() -> None:
        if not package or not pkg_dir.is_dir():
            raise ScaffoldError("this project has no python package (python_package in project.yaml)")

    if kind == "agent":
        if runtime == "python":
            need_python()
            _write(pkg_dir / "agents" / f"{module}.py", PY_AGENT.format(name=name), created)
            entry["entry"] = f"{package}.agents.{module}:create_agent"
        elif runtime == "declarative":
            path = project_root / "declarative" / "agents" / f"{name}.yaml"
            _write(path, YAML_AGENT.format(name=name), created)
            entry["file"] = f"declarative/agents/{name}.yaml"
        else:
            path = project_root / "dotnet" / "apps" / f"{name}.cs"
            _write(path, DOTNET_AGENT.format(name=name, hosting=hosting_from_dotnet_dir), created)
            entry["file"] = f"dotnet/apps/{name}.cs"
        entry["tools"] = []

    elif kind == "workflow":
        if runtime == "python":
            need_python()
            _write(pkg_dir / "workflows" / f"{module}.py", PY_WORKFLOW.format(name=name), created)
            entry["entry"] = f"{package}.workflows.{module}:create_workflow"
        elif runtime == "declarative":
            path = project_root / "declarative" / "workflows" / f"{name}.yaml"
            _write(path, YAML_WORKFLOW.format(name=name, snake=module), created)
            entry["file"] = f"declarative/workflows/{name}.yaml"
        else:
            raise ScaffoldError("dotnet workflows: add them to the .NET project directly (see docs/dotnet.md)")

    elif kind == "tool":
        entry = {"name": name, "kind": tool_kind, "runtime": runtime}
        if tool_kind == "mcp":
            entry.update(transport="stdio", command="uvx some-mcp-server")
            entry["runtime"] = "python"
        elif tool_kind == "shared":
            if shared_tools_dir is None:
                raise ScaffoldError("no shared tools directory")
            base = shared_tools_dir / "python" / name
            _write(base / "tool.yaml", SHARED_TOOL_YAML.format(name=name, package=module, func=module), created)
            _write(base / "pyproject.toml", SHARED_TOOL_PYPROJECT.format(name=name, package=module), created)
            _write(base / "src" / module / "__init__.py", "", created)
            _write(base / "src" / module / "tool.py", PY_TOOL.format(name=name, func=module), created)
            entry = {"name": name, "kind": "ref", "ref": f"tools/python/{name}"}
        elif runtime == "python":
            need_python()
            _write(pkg_dir / "tools" / f"{module}.py", PY_TOOL.format(name=name, func=module), created)
            tests = project_root / "python" / "tests" / f"test_tool_{module}.py"
            _write(tests, PY_TOOL_TEST.format(package=package, module=module, func=module), created)
            entry["entry"] = f"{package}.tools.{module}:{module}"
        else:
            raise ScaffoldError("dotnet tools live in the .NET project (AIFunctionFactory.Create); see docs/dotnet.md")
    else:
        raise ScaffoldError(f"unknown component kind '{kind}'")

    add_to_manifest(project_root / "project.yaml", KINDS[kind], entry)
    return created, entry
