"""Pipeline validation and linting rules."""

from __future__ import annotations

import enum
from collections import deque

from pydantic import BaseModel

from attractor.pipeline.conditions import ConditionError, parse_condition
from attractor.pipeline.fidelity import is_valid_fidelity
from attractor.pipeline.graph import Graph


class Severity(str, enum.Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Diagnostic(BaseModel):
    rule: str
    severity: Severity
    message: str
    node_id: str | None = None
    edge: str | None = None
    suggested_fix: str | None = None


KNOWN_HANDLER_TYPES = {
    "start",
    "exit",
    "codergen",
    "wait.human",
    "conditional",
    "parallel",
    "fan_in",
    "tool",
    "manager_loop",
    "point",
    "doublecircle",
    "box",
    "diamond",
    "parallelogram",
}


def _is_start_node(node_id: str, shape: str) -> bool:
    return node_id == "start" or shape in ("point",)


def _is_exit_node(node_id: str, shape: str) -> bool:
    return node_id in ("exit", "end") or shape in ("doublecircle",)


def validate(graph: Graph) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    # Rule: start_node
    starts = [nid for nid, n in graph.nodes.items() if _is_start_node(nid, n.type)]
    if len(starts) == 0:
        diagnostics.append(
            Diagnostic(
                rule="start_node",
                severity=Severity.ERROR,
                message="No start node found. Add a node named 'start'.",
                suggested_fix="Add: start [shape=point]",
            )
        )
    elif len(starts) > 1:
        diagnostics.append(
            Diagnostic(
                rule="start_node",
                severity=Severity.ERROR,
                message=f"Multiple start nodes found: {starts}",
            )
        )

    # Rule: terminal_node
    exits = [nid for nid, n in graph.nodes.items() if _is_exit_node(nid, n.type)]
    if len(exits) == 0:
        diagnostics.append(
            Diagnostic(
                rule="terminal_node",
                severity=Severity.ERROR,
                message="No exit node found. Add a node named 'exit'.",
                suggested_fix="Add: exit [shape=doublecircle]",
            )
        )

    # Rule: start_no_incoming
    for s in starts:
        if graph.incoming_edges(s):
            diagnostics.append(
                Diagnostic(
                    rule="start_no_incoming",
                    severity=Severity.ERROR,
                    message=f"Start node '{s}' has incoming edges.",
                    node_id=s,
                )
            )

    # Rule: exit_no_outgoing
    for e in exits:
        if graph.outgoing_edges(e):
            diagnostics.append(
                Diagnostic(
                    rule="exit_no_outgoing",
                    severity=Severity.ERROR,
                    message=f"Exit node '{e}' has outgoing edges.",
                    node_id=e,
                )
            )

    # Rule: edge_target_exists
    all_ids = graph.all_node_ids()
    for edge in graph.edges:
        if edge.source not in all_ids:
            diagnostics.append(
                Diagnostic(
                    rule="edge_target_exists",
                    severity=Severity.ERROR,
                    message=f"Edge source '{edge.source}' does not exist.",
                    edge=f"{edge.source} -> {edge.target}",
                )
            )
        if edge.target not in all_ids:
            diagnostics.append(
                Diagnostic(
                    rule="edge_target_exists",
                    severity=Severity.ERROR,
                    message=f"Edge target '{edge.target}' does not exist.",
                    edge=f"{edge.source} -> {edge.target}",
                )
            )

    # Rule: reachability (BFS from start)
    if starts:
        reachable: set[str] = set()
        queue: deque[str] = deque(starts)
        while queue:
            current = queue.popleft()
            if current in reachable:
                continue
            reachable.add(current)
            for edge in graph.outgoing_edges(current):
                if edge.target not in reachable:
                    queue.append(edge.target)

        for nid in graph.nodes:
            if nid not in reachable:
                diagnostics.append(
                    Diagnostic(
                        rule="reachability",
                        severity=Severity.ERROR,
                        message=f"Node '{nid}' is not reachable from start.",
                        node_id=nid,
                    )
                )

    # Rule: condition_syntax
    for edge in graph.edges:
        if edge.condition:
            try:
                parse_condition(edge.condition)
            except ConditionError as e:
                diagnostics.append(
                    Diagnostic(
                        rule="condition_syntax",
                        severity=Severity.ERROR,
                        message=f"Invalid condition on edge {edge.source}->{edge.target}: {e}",
                        edge=f"{edge.source} -> {edge.target}",
                    )
                )

    # Rule: stylesheet_syntax
    stylesheet = graph.stylesheet
    if stylesheet:
        try:
            from attractor.pipeline.stylesheet import parse_stylesheet

            parse_stylesheet(stylesheet)
        except Exception as e:
            diagnostics.append(
                Diagnostic(
                    rule="stylesheet_syntax",
                    severity=Severity.ERROR,
                    message=f"Invalid stylesheet: {e}",
                )
            )

    # Rule: type_known
    for nid, node in graph.nodes.items():
        nt = node.type
        if nt not in KNOWN_HANDLER_TYPES:
            diagnostics.append(
                Diagnostic(
                    rule="type_known",
                    severity=Severity.WARNING,
                    message=f"Unrecognized handler type '{nt}' on node '{nid}'.",
                    node_id=nid,
                )
            )

    # Rule: fidelity_valid
    for nid, node in graph.nodes.items():
        f = node.fidelity
        if f and not is_valid_fidelity(f):
            diagnostics.append(
                Diagnostic(
                    rule="fidelity_valid",
                    severity=Severity.WARNING,
                    message=f"Invalid fidelity mode '{f}' on node '{nid}'.",
                    node_id=nid,
                )
            )
    for edge in graph.edges:
        f = edge.fidelity
        if f and not is_valid_fidelity(f):
            diagnostics.append(
                Diagnostic(
                    rule="fidelity_valid",
                    severity=Severity.WARNING,
                    message=f"Invalid fidelity mode '{f}' on edge {edge.source}->{edge.target}.",
                    edge=f"{edge.source} -> {edge.target}",
                )
            )

    # Rule: retry_target_exists
    for nid, node in graph.nodes.items():
        rt = node.retry_target
        if rt and rt not in all_ids:
            diagnostics.append(
                Diagnostic(
                    rule="retry_target_exists",
                    severity=Severity.WARNING,
                    message=f"retry_target '{rt}' on node '{nid}' does not exist.",
                    node_id=nid,
                )
            )
        frt = node.fallback_retry_target
        if frt and frt not in all_ids:
            diagnostics.append(
                Diagnostic(
                    rule="retry_target_exists",
                    severity=Severity.WARNING,
                    message=f"fallback_retry_target '{frt}' on node '{nid}' does not exist.",
                    node_id=nid,
                )
            )

    # Rule: goal_gate_has_retry
    for nid, node in graph.nodes.items():
        if node.goal_gate and not node.retry_target:
            diagnostics.append(
                Diagnostic(
                    rule="goal_gate_has_retry",
                    severity=Severity.WARNING,
                    message=f"Node '{nid}' has goal_gate=true but no retry_target.",
                    node_id=nid,
                    suggested_fix=f"Add retry_target attribute to node '{nid}'",
                )
            )

    # Rule: prompt_on_llm_nodes
    for nid, node in graph.nodes.items():
        if node.type in ("codergen", "box") and not node.prompt:
            diagnostics.append(
                Diagnostic(
                    rule="prompt_on_llm_nodes",
                    severity=Severity.WARNING,
                    message=f"Codergen node '{nid}' has no prompt attribute.",
                    node_id=nid,
                )
            )

    return diagnostics


class ValidationError(Exception):
    def __init__(self, diagnostics: list[Diagnostic]):
        self.diagnostics = diagnostics
        messages = [f"[{d.severity.value}] {d.rule}: {d.message}" for d in diagnostics]
        super().__init__("\n".join(messages))


def validate_or_raise(graph: Graph) -> list[Diagnostic]:
    diagnostics = validate(graph)
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    if errors:
        raise ValidationError(errors)
    return diagnostics
