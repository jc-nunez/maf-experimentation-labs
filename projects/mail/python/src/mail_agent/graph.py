"""Minimal read-only Microsoft Graph mail client (inbox listing with paging)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx

GRAPH = "https://graph.microsoft.com/v1.0"
INBOX_MESSAGES = f"{GRAPH}/me/mailFolders/inbox/messages"
SELECT = "from,subject,receivedDateTime,isRead,bodyPreview,inferenceClassification"
PAGE_SIZE = 100
TIMEOUT = 30.0
MAX_RETRIES = 3  # on 429 / 503, honouring Retry-After
MAX_RETRY_AFTER = 10.0

# Tests inject an httpx.MockTransport here; None means real network connections.
_transport: httpx.AsyncBaseTransport | None = None


class GraphError(RuntimeError):
    """Raised with a message meant for the model (it is returned as the tool error)."""


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def list_inbox_messages(token: str, since: datetime, max_messages: int) -> tuple[list[dict[str, Any]], bool]:
    """Inbox messages received at or after ``since``, newest first. Returns (messages, truncated)."""
    params: dict[str, Any] | None = {
        "$filter": f"receivedDateTime ge {_iso(since)}",
        "$orderby": "receivedDateTime desc",
        "$select": SELECT,
        "$top": PAGE_SIZE,
    }
    url: str | None = INBOX_MESSAGES
    messages: list[dict[str, Any]] = []
    async with httpx.AsyncClient(
        timeout=TIMEOUT, headers={"Authorization": f"Bearer {token}"}, transport=_transport
    ) as client:
        while url:
            page = await _get(client, url, params)
            messages.extend(page.get("value", []))
            if len(messages) >= max_messages:
                return messages[:max_messages], True
            url, params = page.get("@odata.nextLink"), None  # the next link already carries the query
            if url and not url.startswith(f"{GRAPH}/"):
                raise GraphError("unexpected paging link from Graph; refusing to send the token elsewhere")
    return messages, False


def _retry_after(response: httpx.Response) -> float:
    try:
        seconds = float(response.headers.get("retry-after", 2))
    except ValueError:  # an HTTP date: not worth parsing for a short wait
        seconds = 2.0
    return max(0.0, min(seconds, MAX_RETRY_AFTER))


async def _get(client: httpx.AsyncClient, url: str, params: dict[str, Any] | None) -> dict[str, Any]:
    for attempt in range(MAX_RETRIES + 1):
        response = await client.get(url, params=params)
        if response.status_code in (429, 503) and attempt < MAX_RETRIES:
            await asyncio.sleep(_retry_after(response))
            continue
        break
    if response.status_code == 401:
        raise GraphError("Graph rejected the access token (401); sign in again with mail_agent.auth")
    if response.status_code == 403:
        raise GraphError("Graph denied access (403); the app registration needs the delegated Mail.Read permission")
    if response.status_code >= 400:
        try:
            detail = response.json().get("error", {}).get("message", "")
        except ValueError:
            detail = ""
        raise GraphError(f"Graph returned HTTP {response.status_code} {detail}".strip())
    return response.json()
