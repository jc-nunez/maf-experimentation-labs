"""mafx — create, run, inspect and validate Microsoft Agent Framework projects in this workspace."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import warnings
from pathlib import Path
from typing import Any

import typer
from maf_labs_host import events as ev
from maf_labs_host.manifest import MANIFEST, REASONING_EFFORTS, load_project
from maf_labs_host.providers import (
    PROVIDERS,
    ProviderConfigError,
    openai_compatible_endpoint,
    resolve_provider,
)
from maf_labs_host.runtime import ComponentError, HostContext, build_tool
from maf_labs_host.trace import read_trace
from maf_labs_host.workspace import WorkspaceNotFound, load_env
from rich.console import Console
from rich.table import Table
from rich.text import Text

from . import scaffold, targets
from .render import VIEWS, Renderer, print_info

warnings.filterwarnings("ignore", message=r".*experimental.*", category=Warning)

app = typer.Typer(
    help=__doc__, no_args_is_help=True, rich_markup_mode="rich", add_completion=True, pretty_exceptions_enable=False
)
new_app = typer.Typer(help="Create projects and components from templates.", no_args_is_help=True)
tool_app = typer.Typer(help="Call and inspect tools directly (no model involved).", no_args_is_help=True)
trace_app = typer.Typer(help="Replay and inspect recorded trajectories (.mafx/runs).", no_args_is_help=True)
app.add_typer(new_app, name="new")
app.add_typer(tool_app, name="tool")
app.add_typer(trace_app, name="trace")

out = Console()
err = Console(stderr=True)

ProviderOpt = typer.Option(None, "--provider", help=f"{' | '.join(PROVIDERS)} (default: MAF_PROVIDER / maf-labs.yaml)")
ModelOpt = typer.Option(None, "--model", help="override the provider's model")


def _fail(message: str, code: int = 2) -> None:
    err.print(Text(f"error: {message}", style="bold red"))
    raise typer.Exit(code)


def _ws():
    try:
        return targets.workspace()
    except WorkspaceNotFound as e:
        _fail(str(e))


def _silence_framework_logs() -> None:
    import logging

    logging.getLogger("agent_framework").setLevel(logging.ERROR)


# -------------------------------------------------------------------------------------------------- run


@app.command()
def run(
    target: str | None = typer.Argument(None, help="project/agent, project/workflow, or project"),
    prompt: str | None = typer.Option(None, "-p", "--prompt", help="run once and exit ('-' reads stdin)"),
    output: str = typer.Option("text", "--output", "-o", help="-p mode: text | json | jsonl"),
    provider: str | None = ProviderOpt,
    model: str | None = ModelOpt,
    effort: str | None = typer.Option(
        None, "--effort", "-e", help="reasoning effort for this run: none|low|medium|xhigh (sglang) or high"
    ),
    view: str | None = typer.Option(None, "--view", help="full | normal | quiet (default: maf-labs.yaml)"),
    plain: bool = typer.Option(False, "--plain", help="no live markdown rendering"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="-p text mode: only print the answer"),
    no_trace: bool = typer.Option(False, "--no-trace", help="do not record .mafx/runs/<id>/trace.jsonl"),
    no_build: bool = typer.Option(False, "--no-build", help="dotnet: skip the build step"),
) -> None:
    """Run an agent or workflow. With [bold]-p[/] it runs once and exits; without it starts a session."""
    _silence_framework_logs()
    ws = _ws()
    try:
        tgt = targets.resolve(ws, target)
    except targets.TargetError as e:
        _fail(str(e))
    view = view or ws.default("view", "full")
    if view not in VIEWS:
        _fail(f"--view must be one of {', '.join(VIEWS)}")
    if output not in ("text", "json", "jsonl"):
        _fail("--output must be text, json or jsonl")
    if effort is not None and effort not in REASONING_EFFORTS:
        _fail(f"--effort must be one of {', '.join(REASONING_EFFORTS)}")
    mode = "once" if prompt is not None else "interactive"
    if prompt == "-":
        prompt = sys.stdin.read()

    async def main() -> int:
        runner = targets.make_runner(
            tgt, provider=provider, model=model, record=not no_trace, mode=mode, build=not no_build, effort=effort
        )
        await runner.start()
        try:
            if prompt is None:
                from .interactive import Session

                if not sys.stdin.isatty():
                    _fail("interactive mode needs a terminal; use -p for scripts")
                await Session(runner, out, view, ws.root / ".mafx" / "history").run()
                return 0
            return await _run_once(runner, prompt, output, view, plain, quiet)
        finally:
            await runner.close()

    try:
        code = asyncio.run(main())
    except (ProviderConfigError, ComponentError, targets.TargetError) as e:
        _fail(str(e))
    except KeyboardInterrupt:
        code = 130
    except Exception as e:  # noqa: BLE001
        if os.environ.get("MAFX_DEBUG"):
            raise
        _fail(f"{type(e).__name__}: {e}  (MAFX_DEBUG=1 for a traceback)")
    raise typer.Exit(code)


async def _run_once(runner, prompt: str, output: str, view: str, plain: bool, quiet: bool) -> int:
    collected: list[dict[str, Any]] = []
    renderer = None
    if output == "text" and not quiet:
        print_info(err, runner.info)
        renderer = Renderer(err, view=view, markdown=not plain, show_text=False)
    async for e in runner.turn(prompt):
        collected.append(e)
        if output == "jsonl":
            print(json.dumps(e, default=str), flush=True)
        elif renderer:
            renderer.handle(e)
    if renderer:
        renderer.finish()
    done = collected[-1] if collected else {}
    if output == "text":
        print(done.get("text", "").strip())
    elif output == "json":
        print(json.dumps({"info": runner.info, "result": done, "events": collected}, indent=2, default=str))
    return 0 if done.get("ok") else 1


# ------------------------------------------------------------------------------------------- discovery


@app.command("list")
def list_cmd() -> None:
    """List projects and their agents, tools and workflows."""
    ws = _ws()
    table = Table(box=None, header_style="bold")
    for col in ("project", "kind", "name", "runtime", "description"):
        table.add_column(col)
    for proj in targets.projects(ws):
        first = True
        for kind in ("agents", "tools", "workflows"):
            for spec in getattr(proj.components, kind):
                table.add_row(proj.name if first else "", kind[:-1], spec.name, spec.runtime, spec.description or "")
                first = False
        if first:
            table.add_row(proj.name, "", "(empty)", "", proj.description)
    out.print(table)


@app.command()
def show(project: str = typer.Argument(..., help="project name")) -> None:
    """Show a project's manifest details."""
    ws = _ws()
    try:
        proj = targets.project(ws, project)
    except targets.TargetError as e:
        _fail(str(e))
    out.print(Text(proj.name, style="bold") + Text(f"  [{proj.status}]  {proj.description}", style="dim"))
    out.print(Text(f"  {proj.root}", style="dim"))
    for kind in ("agents", "tools", "workflows"):
        specs = getattr(proj.components, kind)
        if not specs:
            continue
        out.print(Text(f"\n{kind}", style="bold cyan"))
        for spec in specs:
            where = (
                spec.entry
                or spec.file
                or spec.project
                or getattr(spec, "url", None)
                or getattr(spec, "command", None)
                or getattr(spec, "ref", None)
                or ""
            )
            extra = ""
            if kind == "agents" and spec.tools:
                extra = f"  tools: {', '.join(spec.tools)}"
            if kind == "tools":
                extra = f"  kind: {spec.kind}"
            out.print(f"  {spec.name:22} {spec.runtime:12} {where}{extra}")


# --------------------------------------------------------------------------------------------- validate


@app.command()
def validate(
    project: str | None = typer.Argument(None, help="project (default: all)"),
    deep: bool = typer.Option(True, help="also build each python/declarative component on the mock"),
) -> None:
    """Check manifests, entry points, YAML files and tool references."""
    ws = _ws()
    load_env(ws)
    manifests = [ws.projects_dir / project / MANIFEST] if project else sorted(ws.projects_dir.glob(f"*/{MANIFEST}"))
    problems = 0
    from maf_labs_host.mock import MockChatClient
    from maf_labs_host.providers import ProviderInfo
    from maf_labs_host.runtime import build_agent, build_workflow

    for manifest in manifests:
        try:
            proj = load_project(manifest)
        except Exception as e:  # noqa: BLE001
            out.print(Text(f"✗ {manifest.parent.name}: {e}", style="red"))
            problems += 1
            continue
        ctx = HostContext(
            project=proj,
            client=MockChatClient(),
            provider=ProviderInfo("mock", "mock-model", "mock"),
            workspace_root=ws.root,
        )
        names = [s.name for k in ("agents", "tools", "workflows") for s in getattr(proj.components, k)]
        for dup in {n for n in names if names.count(n) > 1}:
            out.print(Text(f"✗ {proj.name}: duplicate component name '{dup}'", style="red"))
            problems += 1
        for kind in ("agents", "tools", "workflows"):
            for spec in getattr(proj.components, kind):
                label = f"{proj.name}/{spec.name}"
                try:
                    for rel in filter(None, [spec.file, spec.project]):
                        if not (proj.root / rel).exists():
                            raise FileNotFoundError(f"{rel} does not exist")
                    if kind == "agents":
                        for tool_name in spec.tools:
                            proj.tool(tool_name)
                    if deep and spec.runtime != "dotnet":
                        if kind == "agents":
                            build_agent(spec, ctx)
                        elif kind == "workflows":
                            build_workflow(spec, ctx)
                        elif spec.kind in ("function", "ref"):
                            build_tool(spec, ctx)
                    note = " (dotnet: not built)" if spec.runtime == "dotnet" else ""
                    out.print(Text(f"✓ {label}", style="green") + Text(note, style="dim"))
                except Exception as e:  # noqa: BLE001
                    problems += 1
                    out.print(Text(f"✗ {label}: {type(e).__name__}: {e}", style="red"))
    if problems:
        _fail(f"{problems} problem(s)", code=1)
    out.print(Text("all good", style="bold green"))


# --------------------------------------------------------------------------------------------- doctor


@app.command()
def doctor(
    provider: str | None = ProviderOpt,
    model: str | None = ModelOpt,
    live: bool = typer.Option(True, help="send test requests to the model endpoint"),
) -> None:
    """Check the toolchain and the model endpoint (models list, a Responses call, a tool call)."""
    ws = _ws()
    load_env(ws)

    def row(ok: bool | None, label: str, detail: str = "") -> None:
        mark = {True: Text("✓", style="green"), False: Text("✗", style="red"), None: Text("•", style="yellow")}[ok]
        out.print(mark + Text(f" {label:28}") + Text(detail, style="dim"))

    row(True, "workspace", str(ws.root))
    row(True, "python", sys.version.split()[0])
    row(shutil.which("uv") is not None or None, "uv", shutil.which("uv") or "not found (needed for uv sync)")
    dotnet = shutil.which("dotnet")
    row(dotnet is not None or None, "dotnet", dotnet or "not found (only needed for dotnet components)")
    row(
        (ws.root / ".env").is_file() or None,
        ".env",
        "found" if (ws.root / ".env").is_file() else "missing — cp .env.example .env",
    )

    try:
        name = resolve_provider(provider, ws.default("provider"))
    except ProviderConfigError as e:
        row(False, "provider", str(e))
        raise typer.Exit(1) from None
    row(True, "provider", name)
    if not live or name == "mock":
        return

    endpoint = None
    try:
        endpoint = openai_compatible_endpoint(name)
    except ProviderConfigError as e:
        row(False, "endpoint", str(e))
        raise typer.Exit(1) from None
    if endpoint:
        import httpx

        base_url, api_key = endpoint
        try:
            resp = httpx.get(
                base_url.rstrip("/") + "/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=10
            )
            resp.raise_for_status()
            served = [m.get("id") for m in resp.json().get("data", [])]
            row(True, "GET /models", ", ".join(served) or "(empty)")
            wanted = model or os.environ.get("SGLANG_MODEL" if name == "sglang" else "OPENAI_MODEL")
            if wanted and served and wanted not in served:
                row(False, "model served", f"'{wanted}' not in /models")
        except Exception as e:  # noqa: BLE001
            row(False, "GET /models", f"{base_url}: {e}")
            raise typer.Exit(1) from None

    async def probe() -> None:
        from agent_framework import Agent, tool
        from maf_labs_host.providers import create_chat_client

        client, info = create_chat_client(name, model)

        @tool(name="get_time", description="Get the current time in a city.")
        def get_time(city: str) -> str:
            return f"12:00 in {city}"

        agent = Agent(client, "Answer briefly.", name="doctor", default_options=dict(info.default_options))
        try:
            r = await agent.run("Reply with the single word: pong")
            row(True, f"{info.api} API", f"model {info.model} replied {r.text.strip()[:40]!r}")
        except Exception as e:  # noqa: BLE001
            row(False, f"{info.api} API", f"{type(e).__name__}: {e}")
            return
        tr = ev.UpdateTranslator()
        try:
            async for u in agent.run("What time is it in Paris? Use the tool.", stream=True, tools=[get_time]):
                tr.translate(u)
            tr.finish()
            if tr.tool_calls:
                row(
                    True,
                    "tool calling",
                    f"{tr.tool_calls} call(s), reasoning streamed: {'yes' if tr.model_calls else 'n/a'}",
                )
            else:
                row(
                    False,
                    "tool calling",
                    "model answered without calling the tool — for SGLang check that the "
                    "server was started with a matching --tool-call-parser",
                )
        except Exception as e:  # noqa: BLE001
            row(False, "tool calling", f"{type(e).__name__}: {e}")

    try:
        asyncio.run(probe())
    except ProviderConfigError as e:
        row(False, "client", str(e))


@app.command()
def models(provider: str | None = ProviderOpt) -> None:
    """List models served by an OpenAI-compatible endpoint (sglang, openai)."""
    ws = _ws()
    load_env(ws)
    import httpx

    try:
        endpoint = openai_compatible_endpoint(resolve_provider(provider, ws.default("provider")))
    except ProviderConfigError as e:
        _fail(str(e))
    if not endpoint:
        _fail("this provider has no /models endpoint")
    base_url, api_key = endpoint
    try:
        resp = httpx.get(base_url.rstrip("/") + "/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        _fail(f"{base_url}: {e}")
    for m in resp.json().get("data", []):
        out.print(f"{m.get('id')}  [dim]{m.get('owned_by', '')} max_model_len={m.get('max_model_len', '?')}[/]")


# ----------------------------------------------------------------------------------------------- new


@new_app.command("project")
def new_project(
    name: str,
    description: str = typer.Option("Incubation project", "--description", "-d"),
    runtimes: str = typer.Option("python,declarative", "--runtimes", "-r", help="python,declarative,dotnet"),
) -> None:
    """Create a project under projects/."""
    ws = _ws()
    chosen = [r.strip() for r in runtimes.split(",") if r.strip()]
    bad = [r for r in chosen if r not in scaffold.RUNTIMES]
    if bad:
        _fail(f"unknown runtime(s): {', '.join(bad)}")
    hosting = os.path.relpath(
        ws.root / "libs/dotnet/MafLabs.Hosting/MafLabs.Hosting.csproj",
        ws.projects_dir / scaffold.kebab(name) / "dotnet" / scaffold.pascal(name),
    )
    try:
        created = scaffold.new_project(ws.projects_dir, name, description, chosen, hosting)
    except scaffold.ScaffoldError as e:
        _fail(str(e))
    for path in created:
        out.print(Text("  + ", style="green") + Text(str(path.relative_to(ws.root))))
    if "python" in chosen:
        out.print(Text("\nnext: uv sync --all-packages   (installs the new python package)", style="dim"))


def _new_component(kind: str, project: str, name: str, runtime: str, tool_kind: str = "function") -> None:
    ws = _ws()
    try:
        proj = targets.project(ws, project)
    except targets.TargetError as e:
        _fail(str(e))
    if runtime not in scaffold.RUNTIMES:
        _fail(f"--runtime must be one of {', '.join(scaffold.RUNTIMES)}")
    hosting = os.path.relpath(
        ws.root / "libs/dotnet/MafLabs.Hosting/MafLabs.Hosting.csproj", proj.root / "dotnet" / "apps"
    )
    try:
        created, entry = scaffold.new_component(
            proj.root,
            proj.python_package,
            kind,
            name,
            runtime,
            tool_kind=tool_kind,
            shared_tools_dir=ws.shared_tools_dir,
            hosting_from_dotnet_dir=hosting,
        )
    except scaffold.ScaffoldError as e:
        _fail(str(e))
    for path in created:
        out.print(Text("  + ", style="green") + Text(str(path.relative_to(ws.root))))
    out.print(
        Text("  ~ ", style="yellow")
        + Text(f"{proj.root.relative_to(ws.root)}/project.yaml")
        + Text(f"  ({kind} '{entry['name']}')", style="dim")
    )


RuntimeOpt = typer.Option("python", "--runtime", "-r", help="python | declarative | dotnet")


@new_app.command("agent")
def new_agent(project: str, name: str, runtime: str = RuntimeOpt) -> None:
    """Add an agent to a project."""
    _new_component("agent", project, name, runtime)


@new_app.command("workflow")
def new_workflow(project: str, name: str, runtime: str = RuntimeOpt) -> None:
    """Add a workflow to a project."""
    _new_component("workflow", project, name, runtime)


@new_app.command("tool")
def new_tool(
    project: str,
    name: str,
    runtime: str = RuntimeOpt,
    kind: str = typer.Option("function", "--kind", "-k", help="function | mcp"),
    shared: bool = typer.Option(False, "--shared", help="create it under tools/ and reference it"),
) -> None:
    """Add a tool: a python function, an MCP server entry, or a shared tool package (--shared)."""
    if kind not in ("function", "mcp"):
        _fail("--kind must be function or mcp")
    _new_component("tool", project, name, runtime, tool_kind="shared" if shared else kind)


# ---------------------------------------------------------------------------------------------- tools


def _tool(ref: str):
    ws = _ws()
    load_env(ws)
    try:
        tgt = targets.resolve(ws, ref, kinds=("tools",))
    except targets.TargetError as e:
        _fail(str(e))
    spec = tgt.project.tool(tgt.name)
    from maf_labs_host.mock import MockChatClient
    from maf_labs_host.providers import ProviderInfo

    ctx = HostContext(project=tgt.project, client=MockChatClient(), provider=ProviderInfo("mock", None, "mock"))
    try:
        return spec, build_tool(spec, ctx)
    except ComponentError as e:
        _fail(str(e))


@tool_app.command("run")
def tool_run(
    ref: str = typer.Argument(..., help="project/tool"),
    args: str = typer.Option("{}", "--args", "-a", help="JSON arguments"),
) -> None:
    """Invoke a function tool directly and print its result."""
    spec, built = _tool(ref)
    try:
        arguments = json.loads(args)
    except ValueError as e:
        _fail(f"--args is not valid JSON: {e}")

    def pick(functions: list[Any]) -> Any:
        wanted = arguments.pop("_function", None)
        fn = next((f for f in functions if f.name == wanted), None)
        if fn is None:
            names = ", ".join(f.name for f in functions)
            _fail(f'{ref} has several functions ({names}); choose one with "_function" in --args')
        return fn

    async def go() -> Any:
        if hasattr(built, "__aenter__"):
            async with built:
                return await pick(built.functions).invoke(arguments=arguments, skip_parsing=True)
        if isinstance(built, list):
            return await pick(built).invoke(arguments=arguments, skip_parsing=True)
        return await built.invoke(arguments=arguments, skip_parsing=True)

    try:
        result = asyncio.run(go())
    except Exception as e:  # noqa: BLE001
        _fail(f"{type(e).__name__}: {e}", code=1)
    out.print_json(json.dumps(ev.to_jsonable(result), default=str))


@tool_app.command("inspect")
def tool_inspect(ref: str = typer.Argument(..., help="project/tool")) -> None:
    """Show the JSON schema the model sees (for MCP servers: every function they expose)."""
    spec, built = _tool(ref)

    async def go() -> list[dict[str, Any]]:
        if hasattr(built, "__aenter__"):
            async with built:
                return [f.to_json_schema_spec() for f in built.functions]
        return [t.to_json_schema_spec() for t in (built if isinstance(built, list) else [built])]

    try:
        schemas = asyncio.run(go())
    except Exception as e:  # noqa: BLE001
        _fail(f"{type(e).__name__}: {e}", code=1)
    out.print_json(json.dumps(schemas, default=str))


# ---------------------------------------------------------------------------------------------- trace


def _run_dir(ws, run_id: str) -> Path:
    runs = ws.runs_dir
    if run_id == "last":
        candidates = sorted((p for p in runs.glob("*") if (p / "trace.jsonl").is_file()), key=lambda p: p.name)
        if not candidates:
            _fail("no recorded runs yet")
        return candidates[-1]
    matches = [p for p in runs.glob(f"{run_id}*") if p.is_dir()]
    if not matches:
        _fail(f"no run matching '{run_id}' in {runs}")
    return sorted(matches)[-1]


@trace_app.command("list")
def trace_list(limit: int = typer.Option(20, "--limit", "-n")) -> None:
    """List recorded runs (newest first)."""
    ws = _ws()
    runs = sorted(
        (p for p in ws.runs_dir.glob("*") if (p / "trace.jsonl").is_file()), key=lambda p: p.name, reverse=True
    )[:limit]
    table = Table(box=None, header_style="bold")
    for col in ("run", "target", "mode", "provider/model", "turns"):
        table.add_column(col)
    for run_dir in runs:
        events = read_trace(run_dir / "trace.jsonl")
        start = next((e for e in events if e["type"] == ev.RUN_STARTED), {})
        turns = sum(1 for e in events if e["type"] == ev.TURN_COMPLETED)
        table.add_row(
            run_dir.name,
            start.get("target", "?"),
            start.get("mode", "?"),
            f"{start.get('provider', '?')}/{start.get('model', '?')}",
            str(turns),
        )
    out.print(table)


@trace_app.command("show")
def trace_show(
    run_id: str = typer.Argument("last", help="run id (prefix) or 'last'"), view: str = typer.Option("full", "--view")
) -> None:
    """Replay a recorded run with the same renderer as live sessions."""
    ws = _ws()
    run_dir = _run_dir(ws, run_id)
    renderer = Renderer(out, view=view, markdown=True)
    for e in read_trace(run_dir / "trace.jsonl"):
        if e["type"] == ev.RUN_STARTED:
            print_info(out, e)
        elif e["type"] == "user_message":
            renderer.finish()
            out.print(Text("\n› ", style="bold cyan") + Text(e["text"]))
        else:
            renderer.handle(e)
    renderer.finish()


def cli() -> None:
    """Console entry point: known errors become one clean line (MAFX_DEBUG=1 shows tracebacks)."""
    import yaml
    from pydantic import ValidationError

    try:
        app()
    except (
        yaml.YAMLError,
        ValidationError,
        targets.TargetError,
        ComponentError,
        ProviderConfigError,
        FileNotFoundError,
    ) as e:
        if os.environ.get("MAFX_DEBUG"):
            raise
        err.print(Text(f"error: {type(e).__name__}: {e}", style="bold red"))
        raise SystemExit(2) from None


if __name__ == "__main__":
    cli()
