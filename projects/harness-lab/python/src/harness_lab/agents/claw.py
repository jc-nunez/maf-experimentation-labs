"""Personal finance "claw" built on the Agent Framework harness.

Python port of the official "Build your own claw" step 1 sample:
https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/harness

``create_harness_agent`` wires function invocation, per-service-call history persistence, compaction,
todos (TodoProvider), plan/execute modes (AgentModeProvider) and file memory. On top of that this agent adds
finance instructions, the get_stock_price tool (attached by the host from project.yaml) and an execute-mode
loop that keeps working until every todo is done.
"""

from agent_framework import FileSystemAgentFileStore, create_harness_agent, todos_remaining, todos_remaining_message

INSTRUCTIONS = """\
## Personal Finance Assistant Instructions

You are a personal finance and investing assistant. You help the user understand their
watchlist and the markets. When asked about a stock, look up its current price with the
get_stock_price tool.

### Working style

- Always verify numbers with a tool rather than relying on memory. Stock prices change.
- Keep the user's watchlist in a memory file called watchlist.md: read it when reviewing the
  watchlist, and update it whenever the user adds or removes a ticker.
- For multi-step requests, plan first: create todos, then switch to execute mode and work through them.

### Important

You provide information and analysis only. You are not a licensed financial advisor and you
must not present your output as personalized investment advice. Remind the user to do their
own research before making decisions.
"""

# Qwen3.8-Flash-Next serves a 262K context; keep room for the response.
MAX_CONTEXT_WINDOW_TOKENS = 262_144
MAX_OUTPUT_TOKENS = 16_384


def create_agent(client, context):
    memory_root = (context.workspace_root or context.project.root) / ".mafx" / "memory" / context.project.name
    return create_harness_agent(
        client=client,
        name="claw",
        description="Personal finance assistant with planning, todos and file memory",
        agent_instructions=INSTRUCTIONS,
        max_context_window_tokens=MAX_CONTEXT_WINDOW_TOKENS,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        # Hosted web search is an OpenAI/Foundry service tool; SGLang has no equivalent.
        disable_web_search=context.provider.provider not in ("openai", "azure-openai", "foundry"),
        # File memory under .mafx/ (gitignored) instead of ./agent-file-memory in whatever cwd mafx runs from.
        file_memory_store=FileSystemAgentFileStore(memory_root),
        # Keep re-invoking while in execute mode with open todos, reminding the agent what is left.
        loop_should_continue=todos_remaining(looping_modes=["execute"]),
        loop_next_message=todos_remaining_message,
        loop_max_iterations=10,
    )
