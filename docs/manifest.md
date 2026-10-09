# Project manifest (`project.yaml`)

```yaml
name: hello-world                 # folder name under projects/
description: …
status: incubating                # incubating | active | archived
tags: [sample]
python_package: hello_world       # import name of python/src/<package> (used by `mafx new`)

components:
  agents:
    - name: greeter
      runtime: python             # python | declarative | dotnet
      entry: hello_world.agents.greeter:create_agent      # python: module:attribute
      tools: [get_weather]        # tools from this manifest, attached by the host at run time
      reasoning_effort: low       # none | minimal | low | medium | high | xhigh (optional)
    - name: greeter-yaml
      runtime: declarative
      file: declarative/agents/greeter.yaml
    - name: greeter-dotnet
      runtime: dotnet
      project: dotnet/HelloWorld/HelloWorld.csproj        # or  file: dotnet/apps/greeter.cs

  tools:
    - name: get_weather
      kind: function              # function | mcp | ref   (openapi: reserved, not implemented yet)
      runtime: python
      entry: hello_world.tools.weather:get_weather
    - name: docs-mcp
      kind: mcp
      transport: http             # stdio (command + args) | http (url) | websocket (url)
      url: https://learn.microsoft.com/api/mcp
    - name: web-fetch
      kind: ref                   # a shared tool: tools/python/web-fetch/tool.yaml
      ref: tools/python/web-fetch

  workflows:
    - name: draft-review
      runtime: python
      entry: hello_world.workflows.draft_review:create_workflow
    - name: greeting-flow
      runtime: declarative
      file: declarative/workflows/greeting.yaml
```

Rules (enforced by `mafx validate`):
- Names are unique within a project. Unknown keys are rejected.
- Python components need `entry`, declarative ones need `file`, and .NET ones need `project` or `file`.
- `tools:` on an agent must name tools in the same manifest.
- Python and declarative components must build on the mock provider. .NET components are only checked for their files.

## Reasoning effort
From most to least specific:
1. `--effort` on `mafx run` (or `/effort` in a session) for one run.
2. `reasoning_effort` on the agent in `project.yaml`. Python agents get it in their default options; .NET agents get it as `--effort`.
3. Whatever the factory code sets: `default_options={"reasoning": {"effort": …}}` in Python, `ChatOptions.Reasoning` in .NET. Workflows use this to give each agent its own level, reading `context.reasoning_effort` so `--effort` can still override (see `hello-world/draft-review`).
4. The server default.

SGLang with Qwen3.8 accepts `none` (no thinking), `low`, `medium` and `xhigh` (the default). It rejects `high`.

Factory signatures (Python):
```python
def create_agent(client) -> Agent: ...  # or (client, context: HostContext)
def create_workflow(client) -> Workflow: ...
```
`HostContext` gives `project`, `provider` (name/model/api), and `tools(*names)` to build manifest tools in code.
