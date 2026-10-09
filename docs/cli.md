# mafx

Install once: `uv tool install --editable ./cli`, or prefix commands with `uv run`. `mafx` finds the workspace by
looking upward for `maf-labs.yaml`; set `MAFX_HOME` to use it from anywhere.

| Command | Purpose |
|---|---|
| `mafx run <project>/<name> [-p PROMPT]` | Run an agent or workflow. `-p` runs once and exits (`-p -` reads stdin); without it you get an interactive session |
| `mafx list` / `mafx show <project>` | List projects and components |
| `mafx new project <name> -r python,declarative,dotnet` | Create a project |
| `mafx new agent\|workflow <project> <name> -r <runtime>` | Create a component and add it to the manifest |
| `mafx new tool <project> <name> [-k mcp] [--shared]` | Create a function tool (with a test), an MCP entry, or a shared tool package |
| `mafx tool inspect <project>/<tool>` | Show the JSON schema the model sees (for MCP: every server function) |
| `mafx tool run <project>/<tool> -a '{json}'` | Call a tool directly, no model involved |
| `mafx validate [project]` | Check manifests, entries, files and tool refs, and build components on the mock |
| `mafx doctor` | Check the toolchain, `.env`, `GET /models`, a Responses call and a tool call |
| `mafx models` | Models served by the endpoint |
| `mafx trace list` / `mafx trace show [run\|last]` | Recorded trajectories; replay one |

`run` options:
- `--provider`, `--model`: override the provider or model for this run.
- `--view full|normal|quiet`: how much of the trajectory to show.
- `--output text|json|jsonl`: output format in `-p` mode.
- `--plain`: no live markdown rendering.
- `-q`: print only the answer.
- `--no-trace`: don't record the run.
- `--no-build`: skip the build step for .NET components.

Targets can be written as `project/name`, as `project` (uses the first agent), or as `name` (inside a project
folder, or when the name is unique across the workspace).

## Interactive session
- **Keys:** ⏎ sends, Alt+⏎ or Ctrl+J adds a newline, Tab completes slash commands, Ctrl+C interrupts the current response, Ctrl+D exits.
- **Slash commands:**
  - `/view full|normal|quiet`: how much to show (reasoning folded, long results folded, …)
  - `/retry`: re-run the last prompt
  - `/reset`: start a new session
  - `/info`: what is running
  - `/system`: show the instructions
  - `/trace`: show the trace file path
  - `/clear`, `/exit`
- **History** is saved per target in `.mafx/history/`.

Set `MAFX_DEBUG=1` to get full tracebacks.
