"""Deterministic fake weather tool — handy for testing tool calling without external APIs."""

from typing import Annotated

from agent_framework import tool
from pydantic import Field

_FORECASTS = {"paris": ("sunny", 22), "lisbon": ("cloudy", 19), "seattle": ("rain", 12)}


@tool(name="get_weather", description="Get the current weather for a city.")
def get_weather(city: Annotated[str, Field(description="City name, e.g. 'Paris'")]) -> dict:
    forecast, temp_c = _FORECASTS.get(city.strip().lower(), ("partly cloudy", 18))
    return {"city": city, "forecast": forecast, "temp_c": temp_c}
