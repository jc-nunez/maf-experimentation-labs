"""Repo agent: answers questions about a workspace. Read-only in slice 1."""

from agent_framework import Agent

INSTRUCTIONS = """You are repo-agent. You answer questions about the user's workspace and never change anything."""


def create_agent(client) -> Agent:
    return Agent(client, INSTRUCTIONS, name="agent", description="Answers questions about a workspace (read-only)")
