"""Session configuration for the coding agent."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SessionConfig(BaseModel):
    max_turns: int = 0
    max_tool_rounds_per_input: int = 0
    default_command_timeout_ms: int = 10000
    max_command_timeout_ms: int = 600000
    reasoning_effort: str | None = None
    tool_output_limits: dict[str, int] = Field(default_factory=dict)
    tool_line_limits: dict[str, int | None] = Field(default_factory=dict)
    enable_loop_detection: bool = True
    loop_detection_window: int = 10
    max_subagent_depth: int = 1
