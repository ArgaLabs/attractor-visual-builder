"""Tool registry for the coding agent."""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel

from attractor.llm.models import ToolDefinition


class RegisteredTool(BaseModel):
    definition: ToolDefinition
    executor: Callable[..., Any] | None = None

    model_config = {"arbitrary_types_allowed": True}


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, tool: RegisteredTool) -> None:
        self._tools[tool.definition.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def definitions(self) -> list[ToolDefinition]:
        return [t.definition for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools.keys())
