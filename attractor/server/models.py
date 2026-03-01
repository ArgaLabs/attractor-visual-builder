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
