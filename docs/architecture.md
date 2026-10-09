# Architecture

```
                 ┌──────────────────────────── mafx (cli/) ────────────────────────────┐
                 │ run (-p | interactive) · new · validate · tool · trace · doctor     │
                 │ Rich renderer + prompt_toolkit session — one UI for every runtime   │
                 └───────────────┬───────────────────────────────┬─────────────────────┘
                     in-process  │                               │ subprocess, JSONL over stdio
        ┌────────────────────────▼──────────┐       ┌────────────▼──────────────────────┐
        │ maf_labs_host (Python)            │       │ MafLabs.Hosting (.NET)            │
        │ providers · manifest · runners    │       │ providers · runner · -p/--stdio   │
        │ trajectory events · trace.jsonl   │       │ same events, same arguments       │
        └───────┬───────────────┬───────────┘       └────────────┬──────────────────────┘
        python factories   declarative YAML               C# projects / single-file apps
        (Agent, Workflow)  (AgentFactory, WorkflowFactory)
```

## Principles
1. **The manifest is the contract.** `project.yaml` lists every agent, tool and workflow with its runtime and entry.
   mafx and the hosts only read manifests; there is no hidden discovery.
2. **Projects hold logic; hosts hold infrastructure.** Providers, config/.env, argument parsing, output modes,
   tracing and (later) telemetry live in the shared hosts, so every project gets them for free and identically.
3. **One event stream.** Every runtime emits the same trajectory events (docs/host-protocol.md). The CLI, trace
   files, evals and the future web viewer consume only that format.
4. **Same arguments everywhere.** `-p`, `--output`, `--provider`, `--model`, `--stdio` behave the same in the
   Python host, the .NET host and mafx.
5. **Offline first.** The `mock` provider exercises tool loops and workflows without a model, so wiring and tool
   schemas are testable locally in milliseconds.

## Runtimes
| Runtime | Built by | Notes |
|---|---|---|
| python | `create_agent(client)` / `create_workflow(client)` in the project's package | full MAF Python API |
| declarative | `AgentFactory` / `WorkflowFactory` (agent-framework-declarative) | experimental upstream; PowerFx `=` expressions need .NET |
| dotnet | `MafLabsHost` in a .csproj or a .NET 10 single-file app | run by mafx through `dotnet run … -- --stdio` |

## Run data
`.mafx/runs/<run-id>/trace.jsonl` — `run_started`, `user_message`, then the events of each turn.
`.mafx/history/` — interactive input history per target.

## Roadmap
- **Step 2 (telemetry):** OpenTelemetry from both hosts, with an OTLP exporter for Aspire Dashboard or Jaeger. Also `mafx devui <project>`, which serves the project's components in the Agent Framework DevUI web app.
- **Step 3 (evals):** `projects/<p>/evals/` holds datasets, suites, evaluators and baselines. Built on MAF `evaluate_agent`, `evaluate_workflow` and the local checks. Commands: `mafx eval run|report|compare|baseline`.
- **Step 4 (viewer):** `mafx web`, a local read-only viewer for trajectories and eval results (runs list, timeline, diffs between runs).
