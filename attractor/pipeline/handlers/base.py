"""Handler interface and registry for pipeline node handlers."""

from __future__ import annotations

import abc
from typing import Any

from attractor.pipeline.context import Context
from attractor.pipeline.graph import Graph, Node
from attractor.pipeline.outcome import Outcome


class HandlerInput:
    def __init__(
        self,
        node: Node,
        graph: Graph,
        context: Context,
        stage_dir: str = "",
        **kwargs: Any,
    ):
        self.node = node
        self.graph = graph
        self.context = context
        self.stage_dir = stage_dir
        self.extra = kwargs


class Handler(abc.ABC):
    @abc.abstractmethod
    async def execute(self, input: HandlerInput) -> Outcome: ...


class HandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, type_name: str, handler: Handler) -> None:
        self._handlers[type_name] = handler

    def get(self, type_name: str) -> Handler | None:
        return self._handlers.get(type_name)

    def has(self, type_name: str) -> bool:
        return type_name in self._handlers

    def types(self) -> list[str]:
        return list(self._handlers.keys())
