"""Provider profile interface."""

from __future__ import annotations

import abc
from typing import Any

from attractor.agent.execution.base import ExecutionEnvironment
from attractor.agent.tools.registry import ToolRegistry
from attractor.llm.models import ToolDefinition


class ProviderProfile(abc.ABC):
    @property
    @abc.abstractmethod
    def id(self) -> str: ...

    @property
    @abc.abstractmethod
    def model(self) -> str: ...

    @property
    @abc.abstractmethod
    def tool_registry(self) -> ToolRegistry: ...

    @abc.abstractmethod
    def build_system_prompt(
        self, environment: ExecutionEnvironment, project_docs: str = ""
    ) -> str: ...

    def tools(self) -> list[ToolDefinition]:
        return self.tool_registry.definitions()

    def provider_options(self) -> dict[str, Any] | None:
        return None

    supports_reasoning: bool = False
    supports_streaming: bool = True
    supports_parallel_tool_calls: bool = True
    context_window_size: int = 200000
