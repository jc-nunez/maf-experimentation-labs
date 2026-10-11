"""Offline mock chat client.

Lets you exercise agents, tools and workflows without a model endpoint. Behaviour is deterministic:

* Every response starts with a short reasoning block, so trajectory rendering can be tested.
* A prompt line of the form ``call:<tool_name> {"json": "args"}`` makes the mock request that tool call.
  Several lines produce several (parallel) calls. After the tool results come back, the mock
  summarises them.
* Otherwise it echoes the last user message, prefixed with ``[mock]``.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import AsyncIterable, Mapping, Sequence
from typing import Any

from agent_framework import (
    BaseChatClient,
    ChatMiddlewareLayer,
    ChatResponse,
    ChatResponseUpdate,
    Content,
    FunctionInvocationLayer,
    Message,
)
from agent_framework.observability import ChatTelemetryLayer

_CALL_RE = re.compile(r"^\s*call:(?P<name>[\w\-.]+)\s*(?P<args>\{.*\})?\s*$", re.MULTILINE)


def _text_of(message: Message) -> str:
    return "".join(c.text or "" for c in message.contents if c.type == "text")


class RawMockChatClient(BaseChatClient):
    """Deterministic, network-free chat client (no tool loop / middleware layers)."""

    OTEL_PROVIDER_NAME = "mock"

    def __init__(self, model: str = "mock-model", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.model = model

    def _plan(self, messages: Sequence[Message]) -> list[Content]:
        last = messages[-1] if messages else None
        if last is not None and any(c.type == "function_result" for c in last.contents):
            results = [c for c in last.contents if c.type == "function_result"]
            lines = [
                f"- `{c.call_id}` → {c.result if c.exception is None else 'error: ' + c.exception}" for c in results
            ]
            return [
                Content.from_text_reasoning(text=f"Received {len(results)} tool result(s); summarising."),
                Content.from_text(text="[mock] Tool results:\n" + "\n".join(lines)),
            ]

        user_text = next((_text_of(m) for m in reversed(messages) if m.role == "user"), "")
        calls = list(_CALL_RE.finditer(user_text))
        if calls:
            contents: list[Content] = [
                Content.from_text_reasoning(text=f"The prompt asks for {len(calls)} tool call(s).")
            ]
            for match in calls:
                args = match.group("args") or "{}"
                contents.append(
                    Content.from_function_call(
                        call_id=f"call_{uuid.uuid4().hex[:8]}", name=match.group("name"), arguments=args
                    )
                )
            return contents

        return [
            Content.from_text_reasoning(text="No tool needed; echoing the user message."),
            Content.from_text(text=f"[mock] {user_text}" if user_text else "[mock] (empty prompt)"),
        ]

    def _inner_get_response(
        self,
        *,
        messages: Sequence[Message],
        stream: bool,
        options: Mapping[str, Any],
        **kwargs: Any,
    ) -> Any:
        contents = self._plan(messages)
        prompt_tokens = sum(len(_text_of(m).split()) for m in messages)
        completion_tokens = sum(len((c.text or str(c.arguments or "")).split()) for c in contents)
        usage = Content.from_usage(
            usage_details={
                "input_token_count": prompt_tokens,
                "output_token_count": completion_tokens,
                "total_token_count": prompt_tokens + completion_tokens,
            }
        )
        response_id = f"mock_{uuid.uuid4().hex[:8]}"

        if not stream:

            async def _get_response() -> ChatResponse:
                return ChatResponse(
                    messages=[Message(role="assistant", contents=[*contents, usage])],
                    response_id=response_id,
                    model=self.model,
                    finish_reason="tool_calls" if any(c.type == "function_call" for c in contents) else "stop",
                )

            return _get_response()

        async def _stream() -> AsyncIterable[ChatResponseUpdate]:
            for content in contents:
                if content.type in ("text", "text_reasoning") and content.text:
                    # Emit word-by-word so streaming renderers get real deltas.
                    words = content.text.split(" ")
                    for i, word in enumerate(words):
                        piece = word if i == len(words) - 1 else word + " "
                        delta = (
                            Content.from_text(text=piece)
                            if content.type == "text"
                            else Content.from_text_reasoning(text=piece)
                        )
                        yield ChatResponseUpdate(
                            role="assistant", contents=[delta], response_id=response_id, model=self.model
                        )
                else:
                    yield ChatResponseUpdate(
                        role="assistant", contents=[content], response_id=response_id, model=self.model
                    )
            yield ChatResponseUpdate(
                role="assistant", contents=[usage], response_id=response_id, model=self.model, finish_reason="stop"
            )

        return self._build_response_stream(_stream(), response_format=options.get("response_format"))


class MockChatClient(
    FunctionInvocationLayer[Any],
    ChatMiddlewareLayer[Any],
    ChatTelemetryLayer[Any],
    RawMockChatClient,
):
    """Mock client with the same layers (tool loop, middleware, telemetry) as the real clients."""


def dumps_args(arguments: Any) -> str:
    """Normalise tool-call arguments (str or mapping) to a JSON string."""
    if arguments is None:
        return "{}"
    if isinstance(arguments, str):
        return arguments
    return json.dumps(arguments)
