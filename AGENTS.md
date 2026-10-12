# Working in this repo (humans and AI assistants)

## Start here
- Read `docs/NOW.md` first: current bet, slice, demo command, next action.
- Follow the Demo Loop in `docs/process/README.md`: work on the current slice only, put tangents in `docs/inbox.md`,
  close by updating `docs/NOW.md` and the bet's demo log.

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
  `.csproj`) with `#:property PublishAot=false` (AOT disables the reflection JSON that tool calling needs).
  Package versions only in `Directory.Packages.props`.
- stdout is reserved for answers (`-p`) and the JSONL protocol (`--stdio`); log to stderr.

## Handoffs
Cowork writes tasks for Claude Code into a queue shared by all worktrees: `<main checkout>/.handoffs/hNNN-*.md`
(gitignored). One handoff = one branch = one worktree. Jean runs `/handoff [id]` in Claude Code
(`.claude/commands/handoff.md`); Claude Code claims it, executes, fills the Report, sets the status and moves it to
`.handoffs/done/`. Parallel handoffs must not overlap in `touches:` paths; at most 3 in progress at once.
Roles: `docs/process/roles.md`. Cycle: `/sync-docs` (Claude Code, main checkout) → repo-agent `start_worktree hNNN`
(Cowork, or `mafx run repo-agent/agent`) → (in the worktree) `/handoff hNNN` → merge → repo-agent
`finish_worktree hNNN`. `/wt-new` and `/wt-done` are deprecated (fallback only).

## Commits
[Conventional Commits 1.0](https://www.conventionalcommits.org/en/v1.0.0/): `<type>(<scope>): <summary>`
- Types: `feat` `fix` `docs` `test` `refactor` `perf` `build` `ci` `chore`. Breaking change: `!` after the scope plus a
  `BREAKING CHANGE:` footer (protocol, manifest or CLI argument changes).
- Scopes: `host` (Python host), `dotnet` (.NET host), `cli` (mafx), `tools`, `infra`, `docs`, or a project name
  (`mail`, `harness-lab`, `hello-world`).
- Summary: imperative, lower case, no period, at most 72 characters.
- Bet work adds a footer: `Refs: bet-001/s01`.
- One task per commit when a slice plan lists tasks.

Example: `feat(mail): add read-only mail_digest tool for outlook.com`

## Pull requests
Use `.github/pull_request_template.md`. Title follows Conventional Commits. Body sections:
- **Background:** why, 1 to 3 lines, `Refs: bet-NNN/sNN`.
- **Scope:** in and out, as a table.
- **Approach:** a **Map** (ASCII diagram of the components or classes with file paths, `[NEW]` / `[CHANGED]` marked),
  a **Review order** table (file, what to look at), **Decisions and trade-offs** (chosen, alternative, why),
  **Risks and follow-ups**.
- **Verify:** demo command and checks with expected results.

Writing rules: **concise**. The body fits one screen (about 40 lines plus the Map). Background at most 3 lines;
Scope and Review order at most 7 rows; Decisions and Risks at most 3 each. Tables and diagrams over prose, no filler,
no restating the diff, delete empty sections, every claim points to a file.

## Checks before committing
```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest                 # offline, mock provider
uv run mafx validate
dotnet build maf-labs.slnx    # when .NET code changed
```
