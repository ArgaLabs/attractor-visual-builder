"""Anthropic provider profile (Claude Code aligned)."""

from __future__ import annotations

from typing import Any

from attractor.agent.execution.base import ExecutionEnvironment
from attractor.agent.profiles.base import ProviderProfile
from attractor.agent.prompts import build_environment_context
from attractor.agent.tools.core import register_core_tools
from attractor.agent.tools.registry import ToolRegistry


class AnthropicProfile(ProviderProfile):
    def __init__(self, model_name: str = "claude-sonnet-4-5"):
        self._model = model_name
        self._registry = ToolRegistry()
        register_core_tools(self._registry)

    @property
    def id(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._model

    @property
    def tool_registry(self) -> ToolRegistry:
        return self._registry

    supports_reasoning = True
    supports_parallel_tool_calls = True
    context_window_size = 200000

    def build_system_prompt(self, environment: ExecutionEnvironment, project_docs: str = "") -> str:
        env_ctx = build_environment_context(environment)
        parts = [
            "You are a coding agent. You help users with software engineering tasks.",
            "You have tools for reading files, editing files, writing files,"
            " running shell commands, and searching code.",
            "Always read a file before editing it. Use the edit_file tool"
            " with old_string/new_string for targeted edits."
            " The old_string must uniquely identify the text to replace.",
            "Prefer editing existing files over creating new ones.",
            env_ctx,
        ]
        if project_docs:
            parts.append(f"<project_instructions>\n{project_docs}\n</project_instructions>")
        return "\n\n".join(parts)

    def provider_options(self) -> dict[str, Any] | None:
        return {"anthropic": {"beta_headers": ["interleaved-thinking-2025-05-14"]}}
