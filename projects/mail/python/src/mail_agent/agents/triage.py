"""triage agent."""

from agent_framework import Agent

INSTRUCTIONS = """You are triage, a helpful assistant."""


def create_agent(client) -> Agent:
    # Tools listed under this agent in project.yaml are attached by the host at run time.
    # Use `def create_agent(client, context)` to build manifest tools here: context.tools("name").
    return Agent(client, INSTRUCTIONS, name="triage")
