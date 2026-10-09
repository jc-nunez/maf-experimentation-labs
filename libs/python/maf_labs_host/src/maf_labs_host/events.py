"""Trajectory events: one normalized, JSON-serializable stream for every runtime.

Python, declarative and .NET hosts all emit these (the .NET host over stdio as JSON Lines), so the CLI,
trace files and future web viewer only need to understand one format. See docs/host-protocol.md.
"""

from __future__ import annotations

import dataclasses
import json
import re
import time
from collections.abc import AsyncIterator, Iterable
from typing import Any

# Event types
RUN_STARTED = "run_started"
REASONING = "reasoning_delta"
TEXT = "text_delta"
TOOL_CALL = "tool_call"
TOOL_RESULT = "tool_result"
USAGE = "usage"
EXECUTOR_STARTED = "executor_started"
EXECUTOR_COMPLETED = "executor_completed"
WORKFLOW_OUTPUT = "workflow_output"
REQUEST_INFO = "request_info"
APPROVAL_REQUEST = "approval_request"
APPROVAL_DECISION = "approval_decision"
# Decisions a host accepts for an approval request.
APPROVAL_CHOICES = ("approve", "deny", "always", "always_args")
WARNING = "warning"
ERROR = "error"
TURN_COMPLETED = "turn_completed"


_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def visible(text: str) -> str:
    """Escape control characters (ANSI/OSC sequences, carriage returns, ...) so a terminal shows them instead of
    executing them. Model output and tool results (e.g. fetched web pages) are untrusted. Keeps newline and tab."""
    return _CONTROL.sub(lambda m: f"\\x{ord(m.group()):02x}", text)


def visible_event(value: Any) -> Any:
    """``visible`` applied to every string inside an event (keys included)."""
    if isinstance(value, str):
        return visible(value)
    if isinstance(value, dict):
        return {visible_event(k): visible_event(v) for k, v in value.items()}
    if isinstance(value, list):
        return [visible_event(v) for v in value]
    return value


def event(type_: str, **data: Any) -> dict[str, Any]:
    return {"type": type_, "ts": round(time.time(), 3), **data}


def to_jsonable(value: Any) -> Any:
    """Best-effort conversion of framework objects to plain JSON values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    if hasattr(value, "text") and hasattr(value, "messages"):  # AgentResponse / ChatResponse
        return value.text
    if hasattr(value, "model_dump"):
        return to_jsonable(value.model_dump(mode="json"))
    if hasattr(value, "to_dict"):
        try:
            return to_jsonable(value.to_dict())
        except Exception:  # noqa: BLE001 - fall through to str
            pass
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(dataclasses.asdict(value))
    return str(value)


def parse_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return to_jsonable(value)


class UpdateTranslator:
    """Turns a stream of ``AgentResponseUpdate`` objects into trajectory events.

    Function-call arguments can arrive in several deltas, so calls are buffered and flushed as one
    ``tool_call`` event as soon as any other content arrives.
    """

    def __init__(self, executor_id: str | None = None) -> None:
        self.executor_id = executor_id
        self._pending: dict[str, dict[str, Any]] = {}
        self._last_call_id: str | None = None
        self._call_started: dict[str, float] = {}
        self.text_parts: list[str] = []
        self.input_tokens = 0
        self.output_tokens = 0
        self.model_calls = 0
        self.tool_calls = 0
        self.approval_requests: list[Any] = []  # framework Content objects, answered via Runner.approve

    def _ev(self, type_: str, **data: Any) -> dict[str, Any]:
        if self.executor_id is not None:
            data["executor_id"] = self.executor_id
        return event(type_, **data)

    def _flush(self) -> list[dict[str, Any]]:
        out = []
        for call_id, call in self._pending.items():
            self._call_started[call_id] = time.perf_counter()
            self.tool_calls += 1
            out.append(
                self._ev(TOOL_CALL, call_id=call_id, name=call["name"], arguments=parse_json(call["arguments"] or "{}"))
            )
        self._pending.clear()
        return out

    def translate(self, update: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for content in getattr(update, "contents", None) or []:
            ctype = content.type
            if ctype == "function_call":
                call_id = content.call_id or self._last_call_id or f"call_{len(self._pending)}"
                self._last_call_id = call_id
                call = self._pending.setdefault(call_id, {"name": content.name or "", "arguments": ""})
                if content.name and not call["name"]:
                    call["name"] = content.name
                args = content.arguments
                if isinstance(args, str):
                    call["arguments"] += args
                elif args:
                    call["arguments"] = json.dumps(to_jsonable(args))
                continue

            out.extend(self._flush())
            if ctype == "text_reasoning":
                if content.text:
                    out.append(self._ev(REASONING, text=content.text))
            elif ctype == "text":
                if content.text:
                    self.text_parts.append(content.text)
                    out.append(self._ev(TEXT, text=content.text))
            elif ctype == "function_result":
                started = self._call_started.pop(content.call_id or "", None)
                duration = round(time.perf_counter() - started, 3) if started else None
                out.append(
                    self._ev(
                        TOOL_RESULT,
                        call_id=content.call_id,
                        result=parse_json(content.result),
                        error=content.exception,
                        duration_s=duration,
                    )
                )
            elif ctype == "usage":
                details = content.usage_details or {}
                inp = int(details.get("input_token_count") or 0)
                outp = int(details.get("output_token_count") or 0)
                self.input_tokens += inp
                self.output_tokens += outp
                self.model_calls += 1
                out.append(self._ev(USAGE, input_tokens=inp, output_tokens=outp))
            elif ctype == "error":
                out.append(self._ev(ERROR, message=content.message or "error", code=content.error_code))
            elif ctype == "function_approval_request":
                self.approval_requests.append(content)
                call = content.function_call
                out.append(
                    self._ev(
                        APPROVAL_REQUEST,
                        request_id=content.id,
                        call_id=getattr(call, "call_id", None),
                        name=getattr(call, "name", None),
                        arguments=parse_json(getattr(call, "arguments", None) or "{}"),
                    )
                )
        return out

    def finish(self) -> list[dict[str, Any]]:
        return self._flush()

    @property
    def text(self) -> str:
        return "".join(self.text_parts)


async def collect(events: AsyncIterator[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e async for e in events]


def final_text(events: Iterable[dict[str, Any]]) -> str:
    for e in reversed(list(events)):
        if e["type"] == TURN_COMPLETED:
            return e.get("text") or ""
    return ""
