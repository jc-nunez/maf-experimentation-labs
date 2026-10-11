"""Offline fixtures: Graph responses from fixtures/*.json through an httpx.MockTransport, and a fake token."""

import json
from pathlib import Path

import httpx
import pytest
from mail_agent import auth, graph

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def graph_mock(monkeypatch):
    """Serves inbox_page1.json then inbox_page2.json; records requests. No network, no sign-in needed."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "GET", "the mail project must never write"
        page = "inbox_page2.json" if "skip" in request.url.query.decode() else "inbox_page1.json"
        return httpx.Response(200, json=load(page))

    monkeypatch.setattr(graph, "_transport", httpx.MockTransport(handler))
    monkeypatch.setattr(auth, "get_access_token", lambda alias: f"token-{alias}")
    return requests
