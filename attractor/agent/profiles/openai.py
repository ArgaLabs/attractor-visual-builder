"""OpenAI provider profile (codex-rs aligned)."""

from __future__ import annotations

from typing import Any

from attractor.agent.execution.base import ExecutionEnvironment
from attractor.agent.profiles.base import ProviderProfile
from attractor.agent.prompts import build_environment_context
from attractor.agent.tools.core import register_core_tools
from attractor.agent.tools.registry import RegisteredTool, ToolRegistry
from attractor.llm.models import ToolDefinition


class OpenAIProfile(ProviderProfile):
    def __init__(self, model_name: str = "gpt-5.2-codex"):
        self._model = model_name
        self._registry = ToolRegistry()
        register_core_tools(self._registry)
        self._register_apply_patch()

    @property
    def id(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return self._model

    @property
    def tool_registry(self) -> ToolRegistry:
        return self._registry

    supports_reasoning = True
    supports_parallel_tool_calls = True
    context_window_size = 1047576

    def _register_apply_patch(self) -> None:
        from attractor.agent.tools.apply_patch import apply_patch

        async def _exec(arguments: dict[str, Any], env: ExecutionEnvironment) -> str:
            patch = arguments["patch"]
            affected = apply_patch(patch, env.working_directory())
            return f"Patch applied. Affected files: {', '.join(affected)}"

        self._registry.register(
            RegisteredTool(
                definition=ToolDefinition(
                    name="apply_patch",
                    description="Apply code changes using the v4a patch format.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "patch": {
                                "type": "string",
                                "description": "The patch content in v4a format",
                            },
                        },
                        "required": ["patch"],
                    },
                ),
                executor=_exec,
            )
        )

    def build_system_prompt(self, environment: ExecutionEnvironment, project_docs: str = "") -> str:
        env_ctx = build_environment_context(environment)
        parts = [
            "You are a coding agent. You have access to tools for reading,"
            " writing, and editing files, running shell commands,"
            " and searching code.",
            "Use the apply_patch tool for making code changes -"
            " it supports creating, deleting, and modifying files"
            " using the v4a diff format.",
            "Read files before editing them. Be precise with your edits.",
            env_ctx,
        ]
        if project_docs:
            parts.append(f"<project_instructions>\n{project_docs}\n</project_instructions>")
        return "\n\n".join(parts)

    def provider_options(self) -> dict[str, Any] | None:
        return None
