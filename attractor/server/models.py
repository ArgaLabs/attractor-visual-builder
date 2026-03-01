"""Pydantic request/response schemas for the HTTP API."""

from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel, Field


class PipelineStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CreatePipelineRequest(BaseModel):
    dot_source: str
    context: dict[str, Any] | None = None
    provider: str | None = None
    model: str | None = None
    no_tools: bool = False


class PipelineInfo(BaseModel):
    id: str
    status: PipelineStatus
    name: str = ""
    goal: str = ""
    nodes_total: int = 0
    nodes_completed: int = 0
    current_node: str | None = None
    created_at: float = 0
    duration: float | None = None
    error: str | None = None


class GraphResponse(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    attrs: dict[str, Any] = Field(default_factory=dict)


class QuestionInfo(BaseModel):
    qid: str
    question: str
    options: list[str] = Field(default_factory=list)
    stage: str = ""
    default: str | None = None


class AnswerRequest(BaseModel):
    answer: str


class ValidateRequest(BaseModel):
    dot_source: str


class ValidateResponse(BaseModel):
    valid: bool
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


class GenerateDotRequest(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    graph_attrs: dict[str, Any] = Field(default_factory=dict)


# ── Scheduler models ─────────────────────────────────────────────────────────


class ScheduleStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CreateScheduleRequest(BaseModel):
    dot_source: str
    interval_seconds: int = Field(..., ge=30, description="Minimum 30 seconds between runs")
    duration_seconds: int = Field(
        ..., ge=60, le=7 * 24 * 3600, description="Total lifetime (max 7 days)"
    )
    carry_context: bool = False
    context: dict[str, Any] | None = None


class ScheduleInfo(BaseModel):
    id: str
    status: ScheduleStatus
    interval_seconds: int
    duration_seconds: int
    carry_context: bool
    created_at: float
    expires_at: float
    run_count: int
    run_ids: list[str] = Field(default_factory=list)
    next_run_at: float | None = None
