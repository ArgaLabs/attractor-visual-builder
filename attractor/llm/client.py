"""Core Client with provider routing and middleware."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from typing import Any

from attractor.llm.adapters.base import ProviderAdapter
from attractor.llm.errors import ConfigurationError
from attractor.llm.models import Request, Response, StreamEvent

Middleware = Callable[[Request, Callable[..., Any]], Any]


class Client:
    def __init__(
        self,
        providers: dict[str, ProviderAdapter] | None = None,
        default_provider: str | None = None,
        middleware: list[Middleware] | None = None,
    ):
        self._providers: dict[str, ProviderAdapter] = providers or {}
        self._default_provider = default_provider
        self._middleware = middleware or []

        if not self._default_provider and self._providers:
            self._default_provider = next(iter(self._providers))

    @classmethod
    def from_env(cls) -> Client:
        providers: dict[str, ProviderAdapter] = {}

        if os.environ.get("OPENAI_API_KEY"):
            from attractor.llm.adapters.openai import OpenAIAdapter

            providers["openai"] = OpenAIAdapter()

        if os.environ.get("ANTHROPIC_API_KEY"):
            from attractor.llm.adapters.anthropic import AnthropicAdapter

            providers["anthropic"] = AnthropicAdapter()

        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            from attractor.llm.adapters.gemini import GeminiAdapter

            providers["gemini"] = GeminiAdapter()

        return cls(providers=providers)

    def register_provider(self, name: str, adapter: ProviderAdapter) -> None:
        self._providers[name] = adapter
        if not self._default_provider:
            self._default_provider = name

    def _resolve_provider(self, request: Request) -> ProviderAdapter:
        provider_name = request.provider or self._default_provider
        if not provider_name:
            raise ConfigurationError("No provider specified and no default provider configured")
        adapter = self._providers.get(provider_name)
        if adapter is None:
            raise ConfigurationError(f"Provider '{provider_name}' is not registered")
        return adapter

    async def complete(self, request: Request) -> Response:
        adapter = self._resolve_provider(request)

        async def _call(req: Request) -> Response:
            return await adapter.complete(req)

        fn: Any = _call
        for mw in reversed(self._middleware):
            prev = fn

            async def _wrap(req: Request, _mw: Any = mw, _prev: Any = prev) -> Response:
                return await _mw(req, _prev)

            fn = _wrap

        return await fn(request)

    async def stream(self, request: Request) -> AsyncIterator[StreamEvent]:
        adapter = self._resolve_provider(request)
        return adapter.stream(request)

    async def close(self) -> None:
        for adapter in self._providers.values():
            await adapter.close()


_default_client: Client | None = None


def set_default_client(client: Client) -> None:
    global _default_client
    _default_client = client


def get_default_client() -> Client:
    global _default_client
    if _default_client is None:
        _default_client = Client.from_env()
    return _default_client
