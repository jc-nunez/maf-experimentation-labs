"""A friendly assistant. Tools listed in project.yaml (get_weather) are attached by the host."""

from agent_framework import Agent

INSTRUCTIONS = """You are a friendly, concise assistant.
When the user asks about the weather, call the get_weather tool for each city before answering."""


def create_agent(client) -> Agent:
    return Agent(client, INSTRUCTIONS, name="greeter", description="Friendly assistant with weather lookup")
