# harness-lab

Agents built on the Agent Framework **harness**: `create_harness_agent` (Python) and `HarnessAgent` /
`AsHarnessAgent` (.NET). The harness adds the following on top of a plain agent:
- function invocation
- history persisted after every model call
- compaction
- todos (`TodoProvider`)
- plan/execute modes (`AgentModeProvider`)
- file memory
- tool approval
- optional looping

`claw` is a port of the official "Build your own claw" step 1 sample, a personal finance assistant:
- Python: [samples/02-agents/harness](https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/harness)
- .NET: [samples/02-agents/Harness/BuildYourOwnClaw](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples/02-agents/Harness/BuildYourOwnClaw)

| Component | Runtime | What it shows |
|---|---|---|
| `claw` | python | `create_harness_agent` with the `get_stock_price` tool, web tools, file memory, and an execute-mode loop (`todos_remaining`) |
| `researcher` | python | Port of the official `harness_research.py`: plans research as todos, then searches and reads sources with the web tools |
| `analyst` | python | Port of the official `harness_data_processing.py`: file access over a working copy of `data/`. Reads are auto-approved; writes ask for approval |
| `analyst-dotnet` | dotnet | The same analyst on `HarnessAgent` (`FileAccessStore`, `DisableReadOnlyToolApproval`) |
| `claw-dotnet` | dotnet | `AsHarnessAgent(new HarnessAgentOptions { … })` with the same instructions and tool |
| `get-stock-price` | python tool | mock prices (same price book as the official sample) |
| `web` | shared tool pack | `web_search` (SearXNG) and `fetch_url` (page → markdown), from `tools/python/web-search` |

```bash
mafx run harness-lab/claw                       # interactive: plan → todos → execute → memory
mafx run harness-lab/claw -p "My watchlist is MSFT, NVDA and AAPL. Save it, then tell me which is cheapest."
mafx run harness-lab/claw-dotnet -p "Review my watchlist: MSFT and NVDA."
mafx tool run harness-lab/get-stock-price -a '{"symbol":"NVDA"}'
```

The harness's own tools show up in the trajectory, so you can follow its planning:
- todos: `todos_add`, `todos_complete`, …
- modes: `mode_set`
- file memory: `file_memory_write`, `file_memory_read`, …

## Adaptations for this workspace
- **Web search comes from SearXNG, not the provider.** The harness's built-in web search is a hosted OpenAI/Foundry tool that SGLang doesn't have, so it is disabled. The agents use the shared `web` tools instead, which work with any model. Start it with `mafx infra up searxng` (local Docker) and set `SEARXNG_URL=http://127.0.0.1:8888` in `.env`. `fetch_url` refuses private, loopback and tailnet addresses, checked both before connecting and on the connected socket.
- **File memory is stored under `.mafx/memory/harness-lab/<session>/`** (gitignored), not `./agent-file-memory` in the current directory.
- **Context window:** compaction is sized for Qwen3.8-Flash-Next (262K context, 16K output).
- **SGLang reasoning replay:** the harness persists history after every model call and tags compacted reasoning groups. The `sglang` provider strips reasoning and those tags at the request layer (`SGLangResponsesClient`); see `docs/providers.md`.

## Tool approvals
The analysts work on a copy of `data/` under `.mafx/work/harness-lab/<agent>/`, so their writes never touch the repo.
When an analyst wants to write a file, the turn pauses:
- **In a session:** `mafx` asks: `y` approve, `a` always for this tool, `A` always with these args, `n` deny.
- **With `-p`:** pass `--allow-tool file_access_write` or `--allow-all-tools`. Otherwise the write is denied and the agent is told.

```bash
mafx run harness-lab/analyst
mafx run harness-lab/analyst --allow-tool file_access_write -p "Revenue per region from sales.csv; write it to region_totals.md"
```
