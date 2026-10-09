"""Provider → chat client factory.

Every host builds its model client here, so agents never hard-code a provider. Select with
``--provider`` / ``MAF_PROVIDER``; configure through environment variables (see ``.env.example``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from agent_framework import GROUP_ANNOTATION_KEY, GROUP_HAS_REASONING_KEY, Message
from agent_framework.openai import OpenAIChatClient

PROVIDERS = ("sglang", "openai", "azure-openai", "foundry", "mock")


class ProviderConfigError(RuntimeError):
    pass


@dataclass
class ProviderInfo:
    """What was resolved, for display and trajectory metadata."""

    provider: str
    model: str | None
    api: str  # responses | chat | mock | foundry
    base_url: str | None = None
    default_options: dict[str, Any] = field(default_factory=dict)


class SGLangResponsesClient(OpenAIChatClient):
    """Responses client for SGLang that never replays earlier reasoning.

    SGLang returns reasoning items without ``encrypted_content``, which Agent Framework requires to replay them
    statelessly, and SGLang does not need them back. Stripping happens here, at the innermost layer, because
    middleware (e.g. the harness's per-service-call history persistence) can inject history after any chat
    middleware runs. Only the outgoing request changes: sessions keep their reasoning and live streams show it.
    """

    def _inner_get_response(self, *, messages: Any, options: Any, stream: bool = False, **kwargs: Any) -> Any:
        stripped = [_without_reasoning(m) for m in messages]
        return super()._inner_get_response(messages=stripped, options=options, stream=stream, **kwargs)


def _without_reasoning(message: Message) -> Message:
    """Copy of ``message`` without reasoning content and without the compaction flag saying its group had any."""
    props = message.additional_properties or {}
    annotation = props.get(GROUP_ANNOTATION_KEY)
    flagged = isinstance(annotation, dict) and annotation.get(GROUP_HAS_REASONING_KEY) is True
    if not flagged and not any(c.type == "text_reasoning" for c in message.contents):
        return message
    new_props = dict(props)
    if flagged:
        new_props[GROUP_ANNOTATION_KEY] = {**annotation, GROUP_HAS_REASONING_KEY: False}
    return Message(
        message.role,
        [c for c in message.contents if c.type != "text_reasoning"],
        author_name=message.author_name,
        message_id=message.message_id,
        additional_properties=new_props,
    )


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    if value is not None and (value == "" or value.startswith("<")):
        return default
    return value


def _require(name: str, provider: str) -> str:
    value = _env(name)
    if not value:
        raise ProviderConfigError(f"provider '{provider}' needs {name} (set it in .env)")
    return value


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def resolve_provider(provider: str | None = None, default: str | None = None) -> str:
    name = (provider or _env("MAF_PROVIDER") or default or "sglang").lower()
    if name not in PROVIDERS:
        raise ProviderConfigError(f"unknown provider '{name}'; choose one of {', '.join(PROVIDERS)}")
    return name


def create_chat_client(provider: str | None = None, model: str | None = None) -> tuple[Any, ProviderInfo]:
    """Return ``(chat_client, info)`` for the selected provider."""
    name = resolve_provider(provider)

    if name == "mock":
        from .mock import MockChatClient

        model = model or "mock-model"
        return MockChatClient(model=model), ProviderInfo("mock", model, "mock")

    if name == "sglang":
        base_url = _require("SGLANG_BASE_URL", name)
        model = model or _require("SGLANG_MODEL", name)
        api_key = _env("SGLANG_API_KEY", "EMPTY")
        api = (_env("SGLANG_API", "responses") or "responses").lower()
        if api == "chat":
            from agent_framework.openai import OpenAIChatCompletionClient

            client = OpenAIChatCompletionClient(model=model, api_key=api_key, base_url=base_url)
            return client, ProviderInfo(name, model, "chat", base_url)
        # Default: history stays client-side (store=false) and earlier reasoning is not replayed (see
        # SGLangResponsesClient). With SGLANG_STORE=true the server continues from previous_response_id.
        store = _truthy(_env("SGLANG_STORE", "false"))
        client = SGLangResponsesClient(model=model, api_key=api_key, base_url=base_url)
        return client, ProviderInfo(name, model, "responses", base_url, {"store": store})

    if name == "openai":
        model = model or _require("OPENAI_MODEL", name)
        client = OpenAIChatClient(model=model, api_key=_require("OPENAI_API_KEY", name))
        return client, ProviderInfo(name, model, "responses")

    if name == "azure-openai":
        endpoint = _require("AZURE_OPENAI_ENDPOINT", name)
        model = model or _require("AZURE_OPENAI_DEPLOYMENT", name)
        kwargs: dict[str, Any] = {"model": model, "azure_endpoint": endpoint}
        if key := _env("AZURE_OPENAI_API_KEY"):
            kwargs["api_key"] = key
        else:
            try:
                from azure.identity import DefaultAzureCredential
            except ImportError as e:  # pragma: no cover - optional dependency
                raise ProviderConfigError(
                    "azure-openai without AZURE_OPENAI_API_KEY needs azure-identity (uv sync --extra azure)"
                ) from e
            kwargs["credential"] = DefaultAzureCredential()
        return OpenAIChatClient(**kwargs), ProviderInfo(name, model, "responses", endpoint)

    if name == "foundry":
        try:
            from agent_framework.foundry import FoundryChatClient
            from azure.identity import DefaultAzureCredential
        except ImportError as e:  # pragma: no cover - optional dependency
            raise ProviderConfigError(
                "provider 'foundry' needs agent-framework-foundry and azure-identity (uv sync --extra foundry)"
            ) from e
        endpoint = _require("FOUNDRY_PROJECT_ENDPOINT", name)
        model = model or _require("FOUNDRY_MODEL", name)
        client = FoundryChatClient(project_endpoint=endpoint, model=model, credential=DefaultAzureCredential())
        return client, ProviderInfo(name, model, "foundry", endpoint)

    raise ProviderConfigError(f"provider '{name}' is not implemented")  # pragma: no cover


def openai_compatible_endpoint(provider: str | None = None) -> tuple[str, str] | None:
    """``(base_url, api_key)`` for providers that expose ``/v1/models`` (used by ``mafx models``)."""
    name = resolve_provider(provider)
    if name == "sglang":
        return _require("SGLANG_BASE_URL", name), _env("SGLANG_API_KEY", "EMPTY") or "EMPTY"
    if name == "openai":
        return "https://api.openai.com/v1", _require("OPENAI_API_KEY", name)
    return None
