"""Repo agents on the Agent Framework harness.

- ``agent`` (``mafx run repo-agent/agent``): status, plus start / finish of handoff worktrees. The host attaches the
  manifest tools; the two write tools have ``approval_mode="always_require"``, so mafx asks before every write.
- ``reader`` (behind the ``ask_repo_agent`` MCP tool): read tools and the status skill only, so no write is reachable
  from a question.
"""

from pathlib import Path

from agent_framework import SkillsProvider, create_harness_agent

INSTRUCTIONS = """\
You are repo-agent. You know the user's workspaces under ~/workspaces/<project>/: the main checkouts, their
worktrees, the handoff queue and open pull requests. You can start a handoff's worktree and finish it; the user
approves each of those calls. Everything else only reads.

Follow the skill that fits the request (load it first). If no skill fits, say what you can do: show a workspace's
status, answer questions about it, start a handoff's worktree, finish it.
"""

READER_INSTRUCTIONS = """\
You are repo-agent. You know the user's workspaces under ~/workspaces/<project>/: the main checkouts, their
worktrees, the handoff queue and open pull requests. You only read; you never change anything.

Follow the skill that fits the request (load it first). If no skill fits, say what you can do: show a workspace's
status and answer questions about it.
"""

SKILLS = Path(__file__).resolve().parents[1] / "skills"

# Qwen3.8-Flash-Next serves a 262K context; keep room for the response.
MAX_CONTEXT_WINDOW_TOKENS = 262_144
MAX_OUTPUT_TOKENS = 16_384


def _harness(client, *, name: str, description: str, instructions: str, skills: list[Path]):
    return create_harness_agent(
        client=client,
        name=name,
        description=description,
        agent_instructions=instructions,
        max_context_window_tokens=MAX_CONTEXT_WINDOW_TOKENS,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        skills_paths=skills,
        # Loading a skill or reading its resources is a read: no approval. Skill scripts still ask (there are none).
        auto_approval_rules=[SkillsProvider.read_only_tools_auto_approval_rule],
        disable_todo=True,
        disable_mode=True,
        disable_file_memory=True,
        disable_web_search=True,
    )


def create_agent(client):
    return _harness(
        client,
        name="agent",
        description="Workspace status; starts and finishes handoff worktrees (with approval)",
        instructions=INSTRUCTIONS,
        skills=[SKILLS],
    )


def create_reader(client):
    return _harness(
        client,
        name="reader",
        description="Answers questions about a workspace (read-only)",
        instructions=READER_INSTRUCTIONS,
        skills=[SKILLS / "workspace-status"],
    )
