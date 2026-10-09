"""Research assistant on the Agent Framework harness, with web search through SearXNG.

Python port of the official ``harness_research.py`` sample:
https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/harness

The official sample uses the provider's hosted web search. Self-hosted models have none, so this agent gets
``web_search`` / ``fetch_url`` from the shared ``tools/python/web-search`` pack (SearXNG), attached by the
host from project.yaml.
"""

from agent_framework import FileSystemAgentFileStore, create_harness_agent, todos_remaining, todos_remaining_message

RESEARCH_INSTRUCTIONS = """\
## Research Assistant Instructions

You are a research assistant. When given a research topic, research it
thoroughly using web_search to find sources and fetch_url to read them. Use your knowledge to form good
search queries and hypotheses, but always verify claims with the tools
available to you rather than relying on memory alone.

### Research quality

Consult multiple sources when possible and cross-reference key claims.
When sources disagree, note the discrepancy and explain which source you
consider more reliable and why.
If a web page fails to load or a search returns irrelevant results, try
alternative search queries or sources before moving on.
Track your sources — you will need them when presenting results.

### Presenting results

When presenting your final findings:
- Use Markdown formatting for clarity.
- Use clear sections with headings for each major topic or sub-question.
- Cite your sources inline (e.g., "According to [source name](URL), ...").
- End with a brief summary of key takeaways.
- In addition to returning the results to the user, save the final research
  report to file memory so it survives compaction and can be referenced later.
"""

MAX_CONTEXT_WINDOW_TOKENS = 262_144
MAX_OUTPUT_TOKENS = 16_384


def create_agent(client, context):
    memory_root = (context.workspace_root or context.project.root) / ".mafx" / "memory" / context.project.name
    return create_harness_agent(
        client=client,
        name="researcher",
        description="A research assistant that plans and executes research tasks.",
        agent_instructions=RESEARCH_INSTRUCTIONS,
        max_context_window_tokens=MAX_CONTEXT_WINDOW_TOKENS,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        # web_search/fetch_url come from the manifest; the hosted web search tool is never used here.
        disable_web_search=True,
        file_memory_store=FileSystemAgentFileStore(memory_root),
        loop_should_continue=todos_remaining(looping_modes=["execute"]),
        loop_next_message=todos_remaining_message,
        loop_max_iterations=10,
    )
