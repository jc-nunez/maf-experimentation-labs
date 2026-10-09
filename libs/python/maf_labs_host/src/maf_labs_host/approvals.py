"""Tool approval relay: keep a turn going while the agent waits for approval decisions.

A turn that stops on tools needing approval ends with ``turn_completed.pending_approvals``. Callers answer with
``Runner.approve(decisions)``, which continues the same turn (and may ask again). ``drive`` runs that loop with a
``decide`` callback, so -p mode, the stdio host and interactive sessions share one implementation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from typing import Any

from . import events as ev

Decide = Callable[[list[dict[str, Any]]], Awaitable[dict[str, str]]]
MAX_APPROVAL_ROUNDS = 25


def policy(approve_all: bool = False, allow_tools: Iterable[str] = ()) -> Decide:
    """Non-interactive decisions: approve everything, or only the named tools; deny the rest."""
    allowed = set(allow_tools)

    async def decide(pending: list[dict[str, Any]]) -> dict[str, str]:
        return {p["request_id"]: "approve" if approve_all or p["name"] in allowed else "deny" for p in pending}

    return decide


async def drive(
    runner: Any, stream: AsyncIterator[dict[str, Any]], decide: Decide, max_rounds: int = MAX_APPROVAL_ROUNDS
) -> AsyncIterator[dict[str, Any]]:
    """Yield the events of ``stream`` and of every approval continuation until nothing is pending."""
    for _ in range(max_rounds + 1):
        done: dict[str, Any] | None = None
        async for e in stream:
            if e["type"] == ev.TURN_COMPLETED:
                done = e
            yield e
        pending = (done or {}).get("pending_approvals") or []
        if not pending:
            return
        stream = runner.approve(await decide(pending))
    yield ev.event(ev.ERROR, message=f"stopped after {max_rounds} approval rounds")
