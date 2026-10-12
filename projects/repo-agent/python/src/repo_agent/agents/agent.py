"""Repo agent on the Agent Framework harness. Read-only: its only tools are read tools and skills.

The host attaches the manifest tools (workspace_status). Writes are never tools of this agent: they are separate,
approved MCP tools (see mcp_server.py), so a model cannot reach them from a question.
"""

from pathlib import Path

from agent_framework import SkillsProvider, create_harness_agent

INSTRUCTIONS = """\
You are repo-agent. You know the user's workspaces under ~/workspaces/<project>/: the main checkouts, their
worktrees, the handoff queue and open pull requests. You only read; you never change anything.

Follow the skill that fits the request (load it first). If no skill fits, say what you can do: show a workspace's
status and answer questions about it.
"""

SKILLS = Path(__file__).resolve().parents[1] / "skills"

# Qwen3.8-Flash-Next serves a 262K context; keep room for the response.
MAX_CONTEXT_WINDOW_TOKENS = 262_144
MAX_OUTPUT_TOKENS = 16_384


def create_agent(client):
    return create_harness_agent(
        client=client,
        name="agent",
        description="Answers questions about a workspace (read-only)",
        agent_instructions=INSTRUCTIONS,
        max_context_window_tokens=MAX_CONTEXT_WINDOW_TOKENS,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        skills_paths=[SKILLS],
        # Loading a skill or reading its resources is a read: no approval. Skill scripts still ask (there are none).
        auto_approval_rules=[SkillsProvider.read_only_tools_auto_approval_rule],
        disable_todo=True,
        disable_mode=True,
        disable_file_memory=True,
        disable_web_search=True,
    )
