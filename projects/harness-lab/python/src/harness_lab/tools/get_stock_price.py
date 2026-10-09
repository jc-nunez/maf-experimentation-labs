"""Illustrative stock prices (mock data, not real quotes) — same price book as the official claw sample."""

from datetime import datetime, timezone
from typing import Annotated

from agent_framework import tool
from pydantic import Field

_PRICE_BOOK = {"MSFT": 462.97, "AAPL": 229.35, "GOOGL": 178.12, "AMZN": 201.45, "NVDA": 134.81}


@tool(name="get_stock_price", description="Gets the latest (delayed, illustrative) stock price for a ticker symbol.")
def get_stock_price(symbol: Annotated[str, Field(description="The stock ticker symbol, e.g. MSFT or AAPL.")]) -> dict:
    ticker = symbol.strip().upper()
    price = _PRICE_BOOK.get(ticker)
    if price is None:
        # Deterministic pseudo-price for unknown symbols so runs are repeatable.
        seed = 0
        for ch in ticker:
            seed = (seed * 31 + ord(ch)) % 1_000_000
        price = 50 + (seed % 45000) / 100
    return {"symbol": ticker, "price": price, "currency": "USD", "as_of": datetime.now(timezone.utc).isoformat()}
