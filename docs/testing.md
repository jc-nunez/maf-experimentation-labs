# Testing with mafx

Hands-on checks for each use case, using only the `mafx` CLI. Run them from anywhere inside the repo.
Add `--provider mock` to any `run` command to work offline. The mock calls a tool when the prompt contains a line
like `call:get_weather {"city":"Paris"}`.

## Check the setup
```bash
mafx doctor          # toolchain, .env, GET /models, a Responses call, a tool call
mafx models          # models served by the endpoint
mafx list            # projects and components
mafx show hello-world
mafx validate        # manifests, entries, YAML files, tool refs
```

## Run once (`-p`) — one command per runtime
```bash
# Agents
mafx run hello-world/greeter             -p "Weather in Paris and Lisbon?"   # python
mafx run hello-world/greeter-yaml        -p "Weather in Paris?"              # declarative YAML
mafx run hello-world/greeter-dotnet      -p "Weather in Paris?"              # .NET project
mafx run hello-world/greeter-dotnet-file -p "Weather in Paris?"              # .NET single-file app

# Workflows
mafx run hello-world/draft-review  -p "A two-line poem about testing"        # python WorkflowBuilder
mafx run hello-world/greeting-flow -p "hi"                                   # declarative workflow
```

## Harness agents (planning, todos, modes, file memory)
```bash
mafx run harness-lab/claw                 # interactive; try a multi-step request and watch todos_add / mode_set
mafx run harness-lab/claw -p "My watchlist is MSFT, NVDA and AAPL. Save it, then tell me which is cheapest." --view quiet
mafx run harness-lab/claw -p "Make a todo per ticker (MSFT, NVDA) to get its price and note it in watchlist.md, then execute without asking."
mafx run harness-lab/claw-dotnet -p "My watchlist is MSFT and NVDA. Which is cheaper?"
ls .mafx/memory/harness-lab/              # one folder of memory files per session
```

## Tools (no model involved)
```bash
mafx tool inspect hello-world/get_weather                       # JSON schema the model sees
mafx tool run     hello-world/get_weather -a '{"city":"Lisbon"}'
```

## Output modes
```bash
mafx run hello-world/greeter -p "Weather in Paris?" --view full     # everything (default)
mafx run hello-world/greeter -p "Weather in Paris?" --view normal   # long blocks folded
mafx run hello-world/greeter -p "Weather in Paris?" --view quiet    # answer + one line per tool call
mafx run hello-world/greeter -p "Weather in Paris?" -q              # answer only
mafx run hello-world/greeter -p "Weather in Paris?" --plain         # no live markdown rendering
mafx run hello-world/greeter -p "Weather in Paris?" -o jsonl        # streamed events, one JSON per line
mafx run hello-world/greeter -p "Weather in Paris?" -o json         # one JSON document at the end
echo "Weather in Seattle?" | mafx run hello-world/greeter -p -      # prompt from stdin
mafx run hello-world/greeter -p "hi"; echo "exit=$?"                # 0 ok · 1 failed turn · 2 config error
```
In text mode, the answer goes to stdout and the trajectory to stderr: `mafx run … -p "…" 2>/dev/null` prints only
the answer.

## Interactive sessions
```bash
mafx run hello-world/greeter          # python agent
mafx run hello-world/greeter-dotnet   # .NET agent, same UI
mafx run hello-world/draft-review     # workflow: one section per agent
```
Inside a session:
- **Slash commands:** `/view full|normal|quiet`, `/retry`, `/reset`, `/info`, `/system`, `/trace`, `/clear`, `/help`, `/exit`.
- **Keys:** Alt+⏎ or Ctrl+J adds a newline; Ctrl+C interrupts a response; Ctrl+D exits.

Multi-turn check:
1. "Weather in Seattle?"
2. "And Paris? Compare them."
3. "Which city did I ask about first?"

## Traces
```bash
mafx trace list
mafx trace show last                  # replay the latest run with the same renderer
mafx trace show <run-id> --view quiet
```

## Provider and model variants
```bash
mafx run hello-world/greeter -p "hi" --provider mock                         # offline
mafx run hello-world/greeter -p "hi" --model <model-id>                      # another served model
SGLANG_STORE=true mafx run hello-world/greeter -p "Weather in Paris?"        # server-side continuation
SGLANG_API=chat   mafx run hello-world/greeter -p "Weather in Paris?"        # Chat Completions instead of Responses
MAFX_DEBUG=1      mafx run hello-world/greeter-dotnet -p "hi"                # full tracebacks / .NET stack traces
mafx run hello-world/greeter-dotnet -p "hi" --no-build                       # skip the .NET build step
```

## Scaffolding round-trip
```bash
mafx new project scratch-lab -r python,declarative,dotnet
mafx new agent    scratch-lab researcher                 # python
mafx new agent    scratch-lab planner  -r declarative
mafx new agent    scratch-lab coder    -r dotnet         # .NET single-file app
mafx new tool     scratch-lab search-docs                # python function tool
mafx new tool     scratch-lab docs-mcp -k mcp            # MCP server entry (edit its command first)
mafx new workflow scratch-lab pipeline
mafx new workflow scratch-lab triage   -r declarative
mafx validate scratch-lab
mafx run scratch-lab/researcher -p "hi" --provider mock
mafx run scratch-lab/coder      -p "hi" --provider mock
mafx tool run scratch-lab/search-docs -a '{"value":"x"}'
rm -rf projects/scratch-lab
```
