"""Provider adapter interface."""

from __future__ import annotations

import abc
from collections.abc import AsyncIterator

from attractor.llm.models import Request, Response, StreamEvent


class ProviderAdapter(abc.ABC):
    """Base interface every provider adapter must implement."""

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @abc.abstractmethod
    async def complete(self, request: Request) -> Response: ...

    @abc.abstractmethod
    async def stream(self, request: Request) -> AsyncIterator[StreamEvent]: ...

    async def close(self) -> None:
        pass

    async def initialize(self) -> None:
        pass

    def supports_tool_choice(self, mode: str) -> bool:
        return True
