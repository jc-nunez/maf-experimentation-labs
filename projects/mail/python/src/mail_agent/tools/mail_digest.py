"""mail_digest: read-only digest of recent inbox mail, grouped by sender.

Grouping happens here so the model classifies a few hundred senders, not thousands of messages.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from agent_framework import tool
from pydantic import Field

from mail_agent import auth, graph

MAX_SAMPLES = 3
PREVIEW_CHARS = 160


@tool(
    name="mail_digest",
    description=(
        "Read-only digest of the inbox for the last N days, grouped by sender and sorted by message count. "
        "Each sender has count, unread, focused_ratio (share Outlook placed in Focused) and up to 3 sample "
        "subjects with previews. Never changes any message."
    ),
)
async def mail_digest(
    account: Annotated[str, Field(description="Account alias used at sign-in, e.g. personal")] = "personal",
    days: Annotated[int, Field(description="How many days back to read (1-90)", ge=1, le=90)] = 7,
    max_messages: Annotated[
        int, Field(description="Upper bound on messages read, newest first (1-5000)", ge=1, le=5000)
    ] = 500,
) -> dict[str, Any]:
    token = await asyncio.to_thread(auth.get_access_token, account)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    messages, truncated = await graph.list_inbox_messages(token, since, max_messages)
    return {
        "account": account,
        "since": since.isoformat(timespec="seconds"),
        "total": len(messages),
        "unread": sum(1 for m in messages if not m.get("isRead")),
        "truncated": truncated,
        "senders": group_by_sender(messages),
    }


def group_by_sender(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sender groups sorted by count (then address). Messages are expected newest first."""
    groups: dict[str, dict[str, Any]] = {}
    focused: dict[str, int] = {}
    for m in messages:
        email = (m.get("from") or {}).get("emailAddress") or {}
        address = (email.get("address") or "(unknown)").strip().lower()
        group = groups.setdefault(address, {"name": "", "address": address, "count": 0, "unread": 0, "samples": []})
        group["name"] = group["name"] or (email.get("name") or "").strip()
        group["count"] += 1
        group["unread"] += 0 if m.get("isRead") else 1
        focused[address] = focused.get(address, 0) + (m.get("inferenceClassification") == "focused")
        if len(group["samples"]) < MAX_SAMPLES:
            group["samples"].append(
                {
                    "subject": m.get("subject") or "",
                    "preview": " ".join((m.get("bodyPreview") or "").split())[:PREVIEW_CHARS],
                    "received": m.get("receivedDateTime"),
                }
            )
    for address, group in groups.items():
        group["focused_ratio"] = round(focused[address] / group["count"], 2)
    ordered = sorted(groups.values(), key=lambda g: (-g["count"], g["address"]))
    keys = ("name", "address", "count", "unread", "focused_ratio", "samples")
    return [{k: g[k] for k in keys} for g in ordered]
