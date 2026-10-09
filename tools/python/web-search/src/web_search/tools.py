"""Web tools for agents running on self-hosted models: search through SearXNG and read pages as markdown.

Configuration (environment / .env):
    SEARXNG_URL           Base URL of a SearXNG instance with the JSON format enabled (required for web_search).
    WEB_FETCH_ALLOW_PRIVATE  Set to "true" to let fetch_url reach private, loopback or tailnet addresses (default off).
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import socket
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

import httpx
from agent_framework import tool
from pydantic import Field

USER_AGENT = "maf-labs-web-tools/0.1 (+https://github.com/jc-nunez/maf-experimentation-labs)"
DEFAULT_TIMEOUT = 20.0  # per connect/read
OVERALL_TIMEOUT = 45.0  # whole call, so a slow-drip server cannot hold the agent indefinitely
MAX_FETCH_BYTES = 2_000_000  # page bytes read (HTML extraction is CPU-bound, keep it bounded)
MAX_SEARCH_BYTES = 2_000_000

# Tests inject an httpx.MockTransport here; None means real network connections.
_transport: httpx.AsyncBaseTransport | None = None


class WebToolError(RuntimeError):
    """Raised with a message meant for the model (it is returned as the tool error)."""


# ------------------------------------------------------------------------------------------------- search


@tool(
    name="web_search",
    description=(
        "Search the web. Returns titles, URLs and snippets. Use fetch_url to read a result before relying on it."
    ),
)
async def web_search(
    query: Annotated[str, Field(description="What to search for")],
    max_results: Annotated[int, Field(description="Number of results to return (1-10)", ge=1, le=10)] = 5,
    time_range: Annotated[
        Literal["day", "week", "month", "year"] | None,
        Field(description="Only results from this recent period"),
    ] = None,
) -> list[dict[str, Any]]:
    base_url = os.environ.get("SEARXNG_URL", "").rstrip("/")
    if not base_url:
        raise WebToolError("web search is not configured (SEARXNG_URL is not set)")
    params: dict[str, Any] = {"q": query, "format": "json"}
    if time_range:
        params["time_range"] = time_range
    status, body = await _deadline(_search(f"{base_url}/search", params))
    if status == 403:
        raise WebToolError("SearXNG refused the JSON API (enable `search.formats: [html, json]` in settings.yml)")
    if status >= 400:
        raise WebToolError(f"SearXNG returned HTTP {status}")
    results = json.loads(body).get("results", [])
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": (r.get("content") or "")[:500],
            "published": r.get("publishedDate"),
            "engines": r.get("engines") or [r.get("engine")],
        }
        for r in results[:max_results]
    ]


async def _search(url: str, params: dict[str, Any]) -> tuple[int, bytes]:
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT, headers={"User-Agent": USER_AGENT}, transport=_transport
    ) as client:
        async with client.stream("GET", url, params=params) as response:
            return response.status_code, await _read_capped(response, MAX_SEARCH_BYTES)


async def _read_capped(response: httpx.Response, limit: int) -> bytes:
    body = bytearray()
    async for chunk in response.aiter_bytes():
        body.extend(chunk)
        if len(body) > limit:
            raise WebToolError(f"response is larger than {limit // 1_000_000} MB")
    return bytes(body)


async def _deadline(awaitable: Any) -> Any:
    try:
        return await asyncio.wait_for(awaitable, OVERALL_TIMEOUT)
    except asyncio.TimeoutError as e:
        raise WebToolError(f"timed out after {OVERALL_TIMEOUT:.0f}s") from e


# -------------------------------------------------------------------------------------------------- fetch


def _private_allowed() -> bool:
    return os.environ.get("WEB_FETCH_ALLOW_PRIVATE", "").strip().lower() in ("1", "true", "yes")


_NAT64 = ipaddress.ip_network("64:ff9b::/96")


def _non_public(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True unless the address is globally routable (covers private, loopback, link-local, CGNAT/tailnet,
    reserved, multicast and documentation ranges, and IPv4 embedded in IPv6 via mapping, 6to4, Teredo or NAT64)."""
    if isinstance(address, ipaddress.IPv6Address):
        embedded = [address.ipv4_mapped, address.sixtofour, *(address.teredo or ())]
        if address in _NAT64:
            embedded.append(ipaddress.IPv4Address(int(address) & 0xFFFFFFFF))
        if any(v4 is not None and _non_public(v4) for v4 in embedded):
            return True
    return not address.is_global or address.is_multicast


async def _check_public(host: str) -> None:
    """Refuse hosts that resolve to private, loopback, link-local or CGNAT (tailnet) addresses.

    Web pages can contain instructions aimed at the agent; this keeps a prompt-injected fetch from reaching
    services on the local network or tailnet. It is a fast pre-check; ``_check_peer`` enforces the rule on
    the address actually connected to (DNS can change between the two).
    """
    if _private_allowed():
        return
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise WebToolError(f"cannot resolve {host}") from e
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if _non_public(address):
            raise WebToolError(f"{host} resolves to a non-public address ({address}); fetching it is not allowed")


def _check_peer(response: httpx.Response) -> None:
    """Reject the response before reading its body if the socket is connected to a non-public address."""
    if _private_allowed():
        return
    stream = response.extensions.get("network_stream")
    peer = stream.get_extra_info("server_addr") if stream is not None else None
    if not peer:
        if _transport is not None:  # test transports have no socket
            return
        raise WebToolError("could not verify the server address; refusing to read the response")
    address = ipaddress.ip_address(peer[0])
    if _non_public(address):
        raise WebToolError(f"connected to a non-public address ({address}); fetching it is not allowed")


def _to_markdown(html: str, url: str) -> tuple[str | None, str]:
    import trafilatura

    metadata = trafilatura.extract_metadata(html, default_url=url)
    text = trafilatura.extract(
        html, url=url, output_format="markdown", include_links=True, include_tables=True, favor_recall=True
    )
    return (metadata.title if metadata else None), (text or "")


@tool(
    name="fetch_url",
    description="Read a web page and return its main content as markdown (navigation and ads removed).",
)
async def fetch_url(
    url: Annotated[str, Field(description="The http(s) URL to read")],
    max_chars: Annotated[int, Field(description="Maximum characters of content to return", ge=500, le=50_000)] = 8000,
) -> dict[str, Any]:
    return await _deadline(_fetch(url, max_chars))


async def _fetch(url: str, max_chars: int) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise WebToolError("only http(s) URLs can be fetched")
    await _check_public(parsed.hostname)

    # trust_env=False: connect directly, so the peer-address check below sees the real server, not a proxy.
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=False,
        trust_env=False,
        transport=_transport,
    ) as client:
        # Follow redirects manually so every hop goes through the address checks.
        for _ in range(5):
            async with client.stream("GET", url) as response:
                _check_peer(response)
                if response.is_redirect and response.headers.get("location"):
                    url = str(response.url.join(response.headers["location"]))
                    host = urlparse(url).hostname
                    if not host or urlparse(url).scheme not in ("http", "https"):
                        raise WebToolError("redirect to an invalid URL")
                    await _check_public(host)
                    continue
                if response.status_code >= 400:
                    raise WebToolError(f"HTTP {response.status_code} from {urlparse(url).hostname}")
                body = await _read_capped(response, MAX_FETCH_BYTES)
                content_type = response.headers.get("content-type", "")
                encoding = response.encoding or "utf-8"
                break
        else:
            raise WebToolError("too many redirects")

    raw = body.decode(encoding, errors="replace")
    title: str | None = None
    if "html" in content_type:
        title, text = _to_markdown(raw, url)
    elif content_type.startswith("text/") or "json" in content_type or "xml" in content_type:
        text = raw
    else:
        raise WebToolError(f"unsupported content type: {content_type or 'unknown'}")

    return {
        "url": url,
        "title": title,
        "content": text[:max_chars],
        "truncated": len(text) > max_chars,
    }


TOOLS = [web_search, fetch_url]
