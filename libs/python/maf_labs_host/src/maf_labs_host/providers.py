"""Provider → chat client factory.

Every host builds its model client here, so agents never hard-code a provider. Select with
``--provider`` / ``MAF_PROVIDER``; configure through environment variables (see ``.env.example``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

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
        from agent_framework.openai import OpenAIChatClient

        client = OpenAIChatClient(model=model, api_key=api_key, base_url=base_url)
        # Self-hosted Responses servers rarely support stored responses / previous_response_id, so keep
        # conversation history client-side unless explicitly enabled.
        options = {"store": _truthy(_env("SGLANG_STORE", "false"))}
        return client, ProviderInfo(name, model, "responses", base_url, options)

    if name == "openai":
        from agent_framework.openai import OpenAIChatClient

        model = model or _require("OPENAI_MODEL", name)
        client = OpenAIChatClient(model=model, api_key=_require("OPENAI_API_KEY", name))
        return client, ProviderInfo(name, model, "responses")

    if name == "azure-openai":
        from agent_framework.openai import OpenAIChatClient

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
