"""web_search / fetch_url with a mock HTTP transport (no network), plus a live SearXNG check."""

import os

import httpx
import pytest
from web_search import tools

HTML = (
    "<html><head><title>Agents 101</title></head><body><nav>menu</nav>"
    "<article><h1>Agents 101</h1><p>An agent combines a model, tools and a loop that decides what to do next."
    " This paragraph is long enough for content extraction to keep it as the main text of the page.</p>"
    "</article></body></html>"
)


@pytest.fixture
def transport(monkeypatch):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/search":
            return httpx.Response(
                200,
                json={"results": [{"title": f"r{i}", "url": f"https://e.com/{i}", "content": "s"} for i in range(8)]},
            )
        if request.url.path == "/moved":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})
        return httpx.Response(200, html=HTML)

    monkeypatch.setattr(tools, "_transport", httpx.MockTransport(handler))
    return calls


async def _public(host):  # skip DNS in unit tests
    return None


async def test_search_returns_requested_number_of_results(transport, monkeypatch):
    monkeypatch.setenv("SEARXNG_URL", "http://searx.test")
    results = await tools.web_search.invoke(arguments={"query": "agents", "max_results": 3}, skip_parsing=True)
    assert [r["url"] for r in results] == ["https://e.com/0", "https://e.com/1", "https://e.com/2"]
    assert transport[0].url.params["format"] == "json"


async def test_search_requires_configuration(monkeypatch):
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    with pytest.raises(Exception, match="SEARXNG_URL"):
        await tools.web_search.invoke(arguments={"query": "x"}, skip_parsing=True)


async def test_fetch_extracts_main_content_as_markdown(transport, monkeypatch):
    monkeypatch.setattr(tools, "_check_public", _public)
    page = await tools.fetch_url.invoke(arguments={"url": "https://e.com/page"}, skip_parsing=True)
    assert page["title"] == "Agents 101"
    assert "model, tools and a loop" in page["content"] and "menu" not in page["content"]


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1/", "http://10.0.0.5/", "http://100.101.102.103/", "file:///etc/passwd"]
)
async def test_fetch_refuses_non_public_targets(url):
    with pytest.raises(Exception, match="not allowed|only http"):
        await tools.fetch_url.invoke(arguments={"url": url}, skip_parsing=True)


async def test_fetch_rechecks_redirect_targets(transport, monkeypatch):
    real_check = tools._check_public

    async def check(host):
        if host != "e.com":
            await real_check(host)

    monkeypatch.setattr(tools, "_check_public", check)
    with pytest.raises(Exception, match="not allowed"):
        await tools.fetch_url.invoke(arguments={"url": "https://e.com/moved"}, skip_parsing=True)


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("SEARXNG_URL"), reason="SEARXNG_URL not set")
async def test_live_searxng():
    results = await tools.web_search.invoke(arguments={"query": "Microsoft Agent Framework"}, skip_parsing=True)
    assert results and all(r["url"].startswith("http") for r in results)


@pytest.mark.parametrize(
    ("address", "blocked"),
    [
        ("8.8.8.8", False),
        ("2001:4860:4860::8888", False),
        ("64:ff9b::808:808", False),  # NAT64 of a public address
        ("10.1.2.3", True),
        ("100.100.1.1", True),  # tailnet / CGNAT
        ("fd7a:115c:a1e0::1", True),  # tailnet IPv6
        ("169.254.169.254", True),  # cloud metadata
        ("192.0.2.1", True),  # documentation range
        ("::ffff:10.0.0.1", True),  # IPv4-mapped
        ("2002:0a00:0001::", True),  # 6to4 of 10.0.0.1
        ("64:ff9b::a00:1", True),  # NAT64 of 10.0.0.1
    ],
)
def test_address_classification(address, blocked):
    import ipaddress

    assert tools._non_public(ipaddress.ip_address(address)) is blocked


async def test_fetch_caps_response_size(monkeypatch):
    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"x" * (tools.MAX_FETCH_BYTES + 1))

    monkeypatch.setattr(tools, "_transport", httpx.MockTransport(handler))
    monkeypatch.setattr(tools, "_check_public", _public)
    with pytest.raises(Exception, match="larger than"):
        await tools.fetch_url.invoke(arguments={"url": "https://e.com/big"}, skip_parsing=True)
