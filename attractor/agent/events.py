"""Event system for the coding agent session."""

from __future__ import annotations

import enum
import time
from typing import Any, Callable

from pydantic import BaseModel, Field


class EventKind(str, enum.Enum):
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    USER_INPUT = "user_input"
    ASSISTANT_TEXT_START = "assistant_text_start"
    ASSISTANT_TEXT_DELTA = "assistant_text_delta"
    ASSISTANT_TEXT_END = "assistant_text_end"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_OUTPUT_DELTA = "tool_call_output_delta"
    TOOL_CALL_END = "tool_call_end"
    STEERING_INJECTED = "steering_injected"
    TURN_LIMIT = "turn_limit"
    LOOP_DETECTION = "loop_detection"
    ERROR = "error"
    WARNING = "warning"


class SessionEvent(BaseModel):
    kind: EventKind
    timestamp: float = Field(default_factory=time.time)
    session_id: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


EventHandler = Callable[[SessionEvent], None]


class EventEmitter:
    def __init__(self) -> None:
        self._handlers: list[EventHandler] = []

    def on(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    def emit(self, event: SessionEvent) -> None:
        for handler in self._handlers:
            try:
                handler(event)
            except Exception:
                pass

    def emit_simple(self, kind: EventKind, session_id: str = "", **data: Any) -> None:
        self.emit(SessionEvent(kind=kind, session_id=session_id, data=data))
