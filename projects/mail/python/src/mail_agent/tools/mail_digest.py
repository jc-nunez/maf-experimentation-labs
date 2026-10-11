"""mail-digest tool."""

from typing import Annotated

from agent_framework import tool
from pydantic import Field


@tool(name="mail_digest", description="Describe what mail-digest does — the model reads this.")
def mail_digest(value: Annotated[str, Field(description="Describe the argument")]) -> dict:
    return {"echo": value}
