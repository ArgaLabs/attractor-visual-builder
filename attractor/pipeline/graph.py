"""Graph, Node, Edge data classes for the pipeline."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field


def _parse_duration(val: str) -> float | None:
    """Parse a duration string like '10s', '5m', '2h' into seconds."""
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(s|sec|m|min|h|hr|ms)?$", val.strip(), re.IGNORECASE)
    if not m:
        return None
    num = float(m.group(1))
    unit = (m.group(2) or "s").lower()
    if unit in ("ms",):
        return num / 1000
    if unit in ("m", "min"):
        return num * 60
    if unit in ("h", "hr"):
        return num * 3600
    return num  # seconds


def _coerce_value(val: str) -> Any:
    """Coerce an attribute string value to a Python type."""
    if val.lower() in ("true", "yes"):
        return True
    if val.lower() in ("false", "no"):
        return False
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    d = _parse_duration(val)
    if d is not None:
        return d
    return val


class Node(BaseModel):
    id: str
    attrs: dict[str, Any] = Field(default_factory=dict)
    css_class: str | None = None

    @property
    def type(self) -> str:
        raw = str(self.attrs.get("shape", self.attrs.get("type", "codergen")))
        # Normalize Graphviz visual shapes to canonical handler type names
        _SHAPE_NORM = {
            "Mdiamond": "start",
            "Msquare": "exit",
            "doublecircle": "exit",
            "point": "start",
        }
        return _SHAPE_NORM.get(raw, raw)

    @property
    def label(self) -> str:
        return str(self.attrs.get("label", self.id))

    @property
    def prompt(self) -> str:
        return str(self.attrs.get("prompt", ""))

    @property
    def goal_gate(self) -> bool:
        v = self.attrs.get("goal_gate", False)
        return bool(v) if isinstance(v, bool) else str(v).lower() in ("true", "yes", "1")

    @property
    def max_retries(self) -> int:
        return int(self.attrs.get("max_retries", 0))

    @property
    def retry_target(self) -> str | None:
        return self.attrs.get("retry_target")

    @property
    def fallback_retry_target(self) -> str | None:
        return self.attrs.get("fallback_retry_target")

    @property
    def timeout(self) -> float | None:
        t = self.attrs.get("timeout")
        if t is None:
            return None
        if isinstance(t, (int, float)):
            return float(t)
        return _parse_duration(str(t))

    @property
    def llm_model(self) -> str | None:
        return self.attrs.get("llm_model")

    @property
    def fidelity(self) -> str | None:
        return self.attrs.get("fidelity")

    @property
    def allow_partial(self) -> bool:
        v = self.attrs.get("allow_partial", False)
        return bool(v) if isinstance(v, bool) else str(v).lower() in ("true", "yes", "1")


class Edge(BaseModel):
    source: str
    target: str
    attrs: dict[str, Any] = Field(default_factory=dict)

    @property
    def label(self) -> str:
        return str(self.attrs.get("label", ""))

    @property
    def condition(self) -> str:
        return str(self.attrs.get("condition", ""))

    @property
    def weight(self) -> float:
        return float(self.attrs.get("weight", 0))

    @property
    def fidelity(self) -> str | None:
        return self.attrs.get("fidelity")

    @property
    def loop_restart(self) -> bool:
        v = self.attrs.get("loop_restart", False)
        return bool(v) if isinstance(v, bool) else str(v).lower() in ("true", "yes", "1")


class Graph(BaseModel):
    nodes: dict[str, Node] = Field(default_factory=dict)
    edges: list[Edge] = Field(default_factory=list)
    attrs: dict[str, Any] = Field(default_factory=dict)

    @property
    def goal(self) -> str:
        return str(self.attrs.get("goal", ""))

    @property
    def stylesheet(self) -> str:
        return str(self.attrs.get("stylesheet", ""))

    def node(self, node_id: str) -> Node | None:
        return self.nodes.get(node_id)

    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        self.edges.append(edge)

    def outgoing_edges(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.source == node_id]

    def incoming_edges(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.target == node_id]

    def start_nodes(self) -> list[Node]:
        return [
            n
            for n in self.nodes.values()
            if n.type in ("start", "point") or n.id == "start"
        ]

    def exit_nodes(self) -> list[Node]:
        return [
            n
            for n in self.nodes.values()
            if n.type in ("exit", "doublecircle") or n.id in ("exit", "end")
        ]

    def all_node_ids(self) -> set[str]:
        return set(self.nodes.keys())
