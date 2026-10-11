# maf-experimentation-labs

Incubation workspace for building agents and agentic applications with
[Microsoft Agent Framework](https://github.com/microsoft/agent-framework) (MAF).
Work is organized into **projects**; each project has **agents**, **tools** and **workflows**, written in
**Python**, **declarative YAML** or **.NET**. The **`mafx`** CLI creates, runs and inspects all of them the same way.

```
maf-labs.yaml            workspace marker + defaults (provider, view, paths)
.env.example             provider settings (copy to .env)
cli/                     mafx — the CLI (Python, Typer + Rich + prompt_toolkit)
libs/python/maf_labs_host/   shared Python host: providers, manifest, runners, trajectory events, -p/--stdio
libs/dotnet/MafLabs.Hosting/ shared .NET host: same providers, same argument contract and event protocol
projects/<name>/
  project.yaml           manifest: the project's agents, tools, workflows (source of truth)
  python/                python package (src/<pkg>/{agents,tools,workflows}) + tests
  declarative/           agents/*.yaml (kind: Prompt), workflows/*.yaml (kind: Workflow)
  dotnet/<Proj>/         .NET project;  dotnet/apps/*.cs  .NET 10 single-file apps
tools/                   shared tools reusable across projects (python packages, MCP servers)
infra/                   local supporting services for agents (e.g. SearXNG), run with `mafx infra up`
docs/                    architecture, manifest, CLI, host protocol, providers, .NET
.mafx/                   local run data: traces, sessions, history (gitignored)
```

## Quickstart

```bash
uv sync --all-packages                 # Python 3.10+, installs every workspace package
cp .env.example .env                   # then set SGLANG_BASE_URL (and the model if different)
uv tool install --editable ./cli       # optional: `mafx` on your PATH (otherwise prefix with `uv run`)
                                       # inside the workspace it hands off to .venv/bin/mafx, so every
                                       # project's dependencies are available (re-run `uv sync --all-packages`
                                       # after adding dependencies)

mafx infra up searxng                  # optional: local web search for agents (needs Docker)
mafx doctor                            # toolchain + endpoint check (models, a Responses call, a tool call, web search)
mafx list                              # projects and components
mafx run hello-world/greeter           # interactive session
mafx run hello-world/greeter -p "What's the weather in Paris and Lisbon?"   # run once and exit
mafx run hello-world/draft-review -p "A haiku about agents"                 # a workflow
```

No endpoint handy? Add `--provider mock`. The offline mock streams reasoning and makes tool calls when the prompt
contains lines like `call:get_weather {"city": "Paris"}`.

## What you see when running

Everything the agent does is shown by default, in the style of agentic coding CLIs:

```
  ✻ Thinking
  │ The user wants two cities. I'll call get_weather for each…
  ⏺ get_weather  call_01
  │ args   {"city": "Paris"}
  ⎿ get_weather  call_01  ·  0.21s
  │ result {"city": "Paris", "forecast": "sunny", "temp_c": 22}
  **Paris** is sunny at 22°C …
──────────────── 2 model calls · 2 tool calls · in 1,204 / out 612 tok · 3.4s
```

- **`-p` (run once):** the answer goes to stdout and the trajectory to stderr. `--output json|jsonl` gives machine-readable output, and the exit code is non-zero on failure.
- **Interactive (no `-p`):** a bordered input box with history (Alt+Enter or Ctrl+J adds a newline), streaming markdown, a status bar, and Ctrl+C to interrupt a response.
  - Slash commands: `/view full|normal|quiet`, `/retry`, `/reset`, `/info`, `/system`, `/trace`, `/help`.
- **Workflows:** each executor gets its own section, showing its reasoning, tool calls and output.
- **Traces:** every run is recorded to `.mafx/runs/<id>/trace.jsonl`. `mafx trace list` lists runs and `mafx trace show last` replays one.

## Creating things

```bash
mafx new project my-lab -r python,declarative,dotnet
mafx new agent    my-lab researcher                 # python (default)
mafx new agent    my-lab planner   -r declarative   # YAML
mafx new agent    my-lab coder     -r dotnet        # .NET single-file app
mafx new tool     my-lab search-docs                # python function tool + unit test
mafx new tool     my-lab docs-mcp  -k mcp           # MCP server entry
mafx new tool     my-lab web-fetch --shared         # shared tool package under tools/, referenced by the project
mafx new workflow my-lab pipeline [-r declarative]
uv sync --all-packages && mafx validate my-lab
```

Attach tools to an agent by listing them under the agent in `project.yaml` (`tools: [search-docs, docs-mcp]`).
Test tools without a model: `mafx tool inspect my-lab/search-docs` and `mafx tool run my-lab/search-docs -a '{"value": "x"}'`.

## Running without mafx

Every project can run on its own through the shared host, with the same arguments:

```bash
uv run python -m hello_world greeter -p "hi"                       # python / declarative components
dotnet run --project projects/hello-world/dotnet/HelloWorld -- -p "hi"
dotnet run projects/hello-world/dotnet/apps/greeter.cs -- -p "hi"  # .NET 10 single-file app
```

## Trying things out

[docs/testing.md](docs/testing.md) lists `mafx` commands for every use case: each runtime, workflows, tools,
output modes, sessions, traces, provider variants and scaffolding.

## Tests

```bash
uv run pytest            # offline (mock provider)
uv run pytest -m live    # against your configured endpoint
uv run ruff check . && uv run ruff format --check .
```

## Status and roadmap

Step 1 is in place: layout, manifests, shared hosts, `mafx` run/new/validate/tool/trace/doctor, and the sglang and mock providers.
Next steps:
1. OpenTelemetry export, plus DevUI and Aspire Dashboard wiring.
2. Evals: datasets, suites, runner, reports and baselines.
3. `mafx web`, a viewer for trajectories and eval results.

See [docs/architecture.md](docs/architecture.md).
