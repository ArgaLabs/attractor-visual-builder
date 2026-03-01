"""Outcome and StageStatus for pipeline execution."""

from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel, Field


class StageStatus(str, enum.Enum):
    SUCCESS = "success"
    FAIL = "fail"
    PARTIAL_SUCCESS = "partial_success"
    SKIPPED = "skipped"
    PENDING = "pending"
    RUNNING = "running"


class Outcome(BaseModel):
    status: StageStatus = StageStatus.SUCCESS
    message: str = ""
    context_updates: dict[str, Any] = Field(default_factory=dict)
    preferred_label: str | None = None
    suggested_next_ids: list[str] | None = None
    auto_status: bool = False

    @property
    def is_success(self) -> bool:
        return self.status in (StageStatus.SUCCESS, StageStatus.PARTIAL_SUCCESS)

    @property
    def is_failure(self) -> bool:
        return self.status == StageStatus.FAIL
