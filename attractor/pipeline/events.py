"""Pipeline event types and emitter."""

from __future__ import annotations

import enum
import time
from typing import Any, Callable

from pydantic import BaseModel, Field


class PipelineEventType(str, enum.Enum):
    PIPELINE_STARTED = "pipeline_started"
    PIPELINE_COMPLETED = "pipeline_completed"
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    STAGE_RETRY = "stage_retry"
    EDGE_SELECTED = "edge_selected"
    GOAL_GATE_FAILED = "goal_gate_failed"
    CHECKPOINT_SAVED = "checkpoint_saved"
    ERROR = "error"


class PipelineEvent(BaseModel):
    type: PipelineEventType
    timestamp: float = Field(default_factory=time.time)
    data: dict[str, Any] = Field(default_factory=dict)


PipelineEventHandler = Callable[[PipelineEvent], None]


class PipelineEventEmitter:
    def __init__(self) -> None:
        self._handlers: list[PipelineEventHandler] = []

    def on(self, handler: PipelineEventHandler) -> None:
        self._handlers.append(handler)

    def emit(self, event: PipelineEvent) -> None:
        for handler in self._handlers:
            try:
                handler(event)
            except Exception:
                pass

    def emit_simple(self, type: PipelineEventType, **data: Any) -> None:
        self.emit(PipelineEvent(type=type, data=data))
