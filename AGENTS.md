# Working in this repo (humans and AI assistants)

## Layout and source of truth
- `projects/<name>/project.yaml` is the source of truth for a project's agents, tools and workflows. Add a component
  there (or with `mafx new …`); the CLI and hosts discover nothing that is not in a manifest.
- Shared hosting lives in `libs/python/maf_labs_host` and `libs/dotnet/MafLabs.Hosting`. Projects must not build
  their own model clients, argument parsing or output handling — they register agents/workflows and the host does
  the rest.
- Shared, reusable tools live in `tools/`; project-only tools live in the project.

## Conventions
- Python factories: `create_agent(client) -> Agent`, `create_workflow(client) -> Workflow`. Add a `context`
  parameter to get `HostContext` (e.g. `context.tools("name")`). Never pick a provider inside a project.
- Workflows: set `intermediate_output_from="all_other"` (or `"all"`) on `WorkflowBuilder` so every agent's
  reasoning and tool calls stream to mafx, and `output_from=[...]` for the agents whose responses are the result.
- Tools: `@tool(name=..., description=...)` with `Annotated[..., Field(description=...)]` parameters; every function
  tool gets a unit test that calls `tool.invoke(arguments=..., skip_parsing=True)`.
- Declarative YAML: no `model:` block (the host injects the client). `=` PowerFx expressions need the .NET runtime +
  `powerfx`; prefer `{Variable}` interpolation.
- .NET: project-based apps in `dotnet/<Proj>/`, single-file apps in `dotnet/apps/` (never in a folder with a
  `.csproj`). Package versions only in `Directory.Packages.props`.
- stdout is reserved for answers (`-p`) and the JSONL protocol (`--stdio`); log to stderr.

## Checks before committing
```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest                 # offline, mock provider
uv run mafx validate
```
