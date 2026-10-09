"""Web tools for agents running on self-hosted models: search through SearXNG and read pages as markdown.

Configuration (environment / .env):
    SEARXNG_URL           Base URL of a SearXNG instance with the JSON format enabled (required for web_search).
    WEB_FETCH_ALLOW_PRIVATE  Set to "true" to let fetch_url reach private, loopback or tailnet addresses (default off).
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

import httpx
from agent_framework import tool
from pydantic import Field

USER_AGENT = "maf-labs-web-tools/0.1 (+https://github.com/jc-nunez/maf-experimentation-labs)"
DEFAULT_TIMEOUT = 20.0
MAX_FETCH_BYTES = 5_000_000

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
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT, headers={"User-Agent": USER_AGENT}, transport=_transport
    ) as client:
        response = await client.get(f"{base_url}/search", params=params)
    if response.status_code == 403:
        raise WebToolError("SearXNG refused the JSON API (enable `search.formats: [html, json]` in settings.yml)")
    response.raise_for_status()
    results = response.json().get("results", [])
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


# -------------------------------------------------------------------------------------------------- fetch


def _private_allowed() -> bool:
    return os.environ.get("WEB_FETCH_ALLOW_PRIVATE", "").strip().lower() in ("1", "true", "yes")


def _non_public(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    tailnet = address.version == 4 and address in ipaddress.ip_network("100.64.0.0/10")
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
        or tailnet
    )


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
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_FETCH_BYTES:
                        raise WebToolError(f"page is larger than {MAX_FETCH_BYTES // 1_000_000} MB")
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
