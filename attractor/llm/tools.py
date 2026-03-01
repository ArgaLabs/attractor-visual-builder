"""Tool definitions and execution for the Unified LLM Client."""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field

from attractor.llm.models import ToolDefinition


class Tool(BaseModel):
    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})
    execute: Callable[..., Any] | None = None

    model_config = {"arbitrary_types_allowed": True}

    def to_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )
