"""Checkpoint save/load for pipeline crash recovery."""

from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel, Field


class NodeState(BaseModel):
    node_id: str
    status: str = "pending"
    outcome_data: dict[str, Any] | None = None
    retries: int = 0


class Checkpoint(BaseModel):
    pipeline_name: str = ""
    current_node_id: str = ""
    completed_nodes: list[str] = Field(default_factory=list)
    node_states: dict[str, NodeState] = Field(default_factory=dict)
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2, default=str)

    @classmethod
    def load(cls, path: str) -> Checkpoint:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)

    def mark_completed(self, node_id: str, outcome_data: dict[str, Any] | None = None) -> None:
        if node_id not in self.completed_nodes:
            self.completed_nodes.append(node_id)
        self.node_states[node_id] = NodeState(
            node_id=node_id, status="completed", outcome_data=outcome_data
        )

    def is_completed(self, node_id: str) -> bool:
        return node_id in self.completed_nodes
