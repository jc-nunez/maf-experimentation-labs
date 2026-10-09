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

Factory signatures (Python):
```python
def create_agent(client) -> Agent: ...  # or (client, context: HostContext)
def create_workflow(client) -> Workflow: ...
```
`HostContext` gives `project`, `provider` (name/model/api), and `tools(*names)` to build manifest tools in code.
