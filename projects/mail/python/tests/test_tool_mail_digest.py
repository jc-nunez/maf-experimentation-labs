"""mail_digest and the Graph client against fixtures (httpx.MockTransport, no network)."""

import httpx
import pytest
from mail_agent import graph
from mail_agent.tools.mail_digest import mail_digest


async def test_digest_groups_by_sender_across_pages(graph_mock):
    digest = await mail_digest.invoke(arguments={"account": "personal", "days": 7}, skip_parsing=True)
    assert digest["account"] == "personal" and digest["total"] == 5 and digest["unread"] == 3
    assert digest["truncated"] is False
    shop, *rest = digest["senders"]
    assert shop["address"] == "orders@shop.example" and shop["name"] == "Shop"  # case-folded, first non-empty name
    assert (shop["count"], shop["unread"], shop["focused_ratio"]) == (3, 1, 0.0)
    assert [s["subject"] for s in shop["samples"]] == [
        "Your order has shipped",
        "Receipt for your payment",
        "Another shipment",
    ]
    assert shop["samples"][0]["preview"].startswith("Hi Jean, your order #1234")  # whitespace collapsed
    assert [s["address"] for s in rest] == ["ana@friends.example", "digest@news.example"]  # ties by address
    assert rest[0]["focused_ratio"] == 1.0


async def test_request_selects_fields_filters_by_date_and_pages(graph_mock):
    await mail_digest.invoke(arguments={"account": "personal", "days": 7}, skip_parsing=True)
    first, second = graph_mock
    assert first.url.path == "/v1.0/me/mailFolders/inbox/messages"
    assert first.url.params["$select"] == graph.SELECT and first.url.params["$top"] == "100"
    assert first.url.params["$filter"].startswith("receivedDateTime ge 20")
    assert first.headers["authorization"] == "Bearer token-personal"
    assert second.url.params["$skip"] == "3"


async def test_max_messages_stops_paging(graph_mock):
    digest = await mail_digest.invoke(arguments={"max_messages": 2}, skip_parsing=True)
    assert digest["total"] == 2 and digest["truncated"] is True and len(graph_mock) == 1


async def test_samples_are_capped(graph_mock, monkeypatch):
    message = {"subject": "s", "bodyPreview": "x" * 500, "from": {"emailAddress": {"address": "a@b.c"}}}

    async def many(token, since, max_messages):
        return [message] * 10, False

    monkeypatch.setattr(graph, "list_inbox_messages", many)
    digest = await mail_digest.invoke(arguments={}, skip_parsing=True)
    sender = digest["senders"][0]
    assert sender["count"] == 10 and len(sender["samples"]) == 3 and len(sender["samples"][0]["preview"]) == 160


@pytest.mark.parametrize(("status", "match"), [(401, "sign in again"), (403, "Mail.Read"), (500, "HTTP 500")])
async def test_graph_errors_are_explained(monkeypatch, status, match):
    monkeypatch.setattr(graph, "_transport", httpx.MockTransport(lambda r: httpx.Response(status, json={})))
    with pytest.raises(graph.GraphError, match=match):
        await graph.list_inbox_messages("t", graph.datetime.now(graph.timezone.utc), 10)


async def test_throttling_is_retried(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(200, json={"value": [{"id": "m1"}]})

    monkeypatch.setattr(graph, "_transport", httpx.MockTransport(handler))
    messages, _ = await graph.list_inbox_messages("t", graph.datetime.now(graph.timezone.utc), 10)
    assert len(calls) == 2 and messages == [{"id": "m1"}]


async def test_paging_link_to_another_host_is_refused(monkeypatch):
    page = {"value": [], "@odata.nextLink": "https://evil.example/steal"}
    monkeypatch.setattr(graph, "_transport", httpx.MockTransport(lambda r: httpx.Response(200, json=page)))
    with pytest.raises(graph.GraphError, match="refusing"):
        await graph.list_inbox_messages("t", graph.datetime.now(graph.timezone.utc), 10)
