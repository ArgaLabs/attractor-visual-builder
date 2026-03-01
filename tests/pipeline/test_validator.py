"""Tests for attractor.pipeline.validator."""

import pytest

from attractor.pipeline.graph import Edge, Graph, Node
from attractor.pipeline.validator import Severity, ValidationError, validate, validate_or_raise


def _graph(*specs, edges=None, attrs=None):
    """Helper to build a Graph.

    Each spec is (id, shape) or (id, shape, extra_attrs).
    """
    g = Graph(attrs=attrs or {})
    for spec in specs:
        nid, shape = spec[0], spec[1]
        extra = spec[2] if len(spec) > 2 else {}
        g.add_node(Node(id=nid, attrs={"shape": shape, **extra}))
    for src, tgt, *rest in edges or []:
        g.add_edge(Edge(source=src, target=tgt, attrs=rest[0] if rest else {}))
    return g


class TestStartNode:
    def test_error_when_zero_start_nodes(self):
        g = _graph(("A", "box", {"prompt": "x"}), ("exit", "doublecircle"))
        diags = validate(g)
        start_diags = [d for d in diags if d.rule == "start_node"]
        assert len(start_diags) == 1
        assert start_diags[0].severity == Severity.ERROR

    def test_error_when_multiple_start_nodes(self):
        g = Graph()
        g.add_node(Node(id="start", attrs={"shape": "point"}))
        g.add_node(Node(id="start2", attrs={"shape": "point"}))
        g.add_node(Node(id="exit", attrs={"shape": "doublecircle"}))
        g.add_edge(Edge(source="start", target="exit"))
        g.add_edge(Edge(source="start2", target="exit"))
        diags = validate(g)
        # start_node rule checks id=="start" or shape=="point"
        start_diags = [d for d in diags if d.rule == "start_node"]
        assert any(d.severity == Severity.ERROR for d in start_diags)


class TestTerminalNode:
    def test_error_when_no_exit(self):
        g = _graph(("start", "point"), ("A", "box", {"prompt": "x"}))
        g.add_edge(Edge(source="start", target="A"))
        diags = validate(g)
        exit_diags = [d for d in diags if d.rule == "terminal_node"]
        assert len(exit_diags) == 1
        assert exit_diags[0].severity == Severity.ERROR


class TestReachability:
    def test_error_for_orphan_node(self):
        g = _graph(
            ("start", "point"),
            ("A", "box", {"prompt": "x"}),
            ("orphan", "box", {"prompt": "y"}),
            ("exit", "doublecircle"),
            edges=[("start", "A"), ("A", "exit")],
        )
        diags = validate(g)
        reach_diags = [d for d in diags if d.rule == "reachability"]
        assert any("orphan" in d.message for d in reach_diags)
        assert all(d.severity == Severity.ERROR for d in reach_diags)


class TestEdgeTargetExists:
    def test_error_for_missing_target(self):
        g = _graph(("start", "point"), ("exit", "doublecircle"))
        g.add_edge(Edge(source="start", target="nonexistent"))
        g.add_edge(Edge(source="start", target="exit"))
        diags = validate(g)
        edge_diags = [d for d in diags if d.rule == "edge_target_exists"]
        assert len(edge_diags) >= 1
        assert all(d.severity == Severity.ERROR for d in edge_diags)


class TestStartNoIncoming:
    def test_error_when_start_has_incoming(self):
        g = _graph(
            ("start", "point"),
            ("A", "box", {"prompt": "x"}),
            ("exit", "doublecircle"),
            edges=[("start", "A"), ("A", "start"), ("A", "exit")],
        )
        diags = validate(g)
        si_diags = [d for d in diags if d.rule == "start_no_incoming"]
        assert len(si_diags) == 1
        assert si_diags[0].severity == Severity.ERROR


class TestExitNoOutgoing:
    def test_error_when_exit_has_outgoing(self):
        g = _graph(
            ("start", "point"),
            ("exit", "doublecircle"),
            ("A", "box", {"prompt": "x"}),
            edges=[("start", "exit"), ("exit", "A")],
        )
        diags = validate(g)
        eo_diags = [d for d in diags if d.rule == "exit_no_outgoing"]
        assert len(eo_diags) == 1
        assert eo_diags[0].severity == Severity.ERROR


class TestConditionSyntax:
    def test_error_for_malformed_condition(self):
        g = _graph(
            ("start", "point"),
            ("exit", "doublecircle"),
            edges=[("start", "exit", {"condition": "&&"})],
        )
        diags = validate(g)
        cond_diags = [d for d in diags if d.rule == "condition_syntax"]
        assert len(cond_diags) == 1
        assert cond_diags[0].severity == Severity.ERROR


class TestTypeKnown:
    def test_warning_for_unknown_type(self):
        g = _graph(
            ("start", "point"),
            ("A", "unknown_type"),
            ("exit", "doublecircle"),
            edges=[("start", "A"), ("A", "exit")],
        )
        diags = validate(g)
        type_diags = [d for d in diags if d.rule == "type_known"]
        assert len(type_diags) == 1
        assert type_diags[0].severity == Severity.WARNING


class TestFidelityValid:
    def test_warning_for_invalid_fidelity(self):
        g = _graph(
            ("start", "point"),
            ("A", "box", {"prompt": "x", "fidelity": "bogus"}),
            ("exit", "doublecircle"),
            edges=[("start", "A"), ("A", "exit")],
        )
        diags = validate(g)
        fid_diags = [d for d in diags if d.rule == "fidelity_valid"]
        assert len(fid_diags) == 1
        assert fid_diags[0].severity == Severity.WARNING


class TestRetryTargetExists:
    def test_warning_for_missing_retry_target(self):
        g = _graph(
            ("start", "point"),
            ("A", "box", {"prompt": "x", "retry_target": "ghost"}),
            ("exit", "doublecircle"),
            edges=[("start", "A"), ("A", "exit")],
        )
        diags = validate(g)
        rt_diags = [d for d in diags if d.rule == "retry_target_exists"]
        assert len(rt_diags) == 1
        assert rt_diags[0].severity == Severity.WARNING


class TestGoalGateHasRetry:
    def test_warning_for_goal_gate_without_retry(self):
        g = _graph(
            ("start", "point"),
            ("A", "box", {"prompt": "x", "goal_gate": True}),
            ("exit", "doublecircle"),
            edges=[("start", "A"), ("A", "exit")],
        )
        diags = validate(g)
        gg_diags = [d for d in diags if d.rule == "goal_gate_has_retry"]
        assert len(gg_diags) == 1
        assert gg_diags[0].severity == Severity.WARNING


class TestPromptOnLlmNodes:
    def test_warning_for_codergen_without_prompt(self):
        g = _graph(
            ("start", "point"),
            ("A", "codergen"),
            ("exit", "doublecircle"),
            edges=[("start", "A"), ("A", "exit")],
        )
        diags = validate(g)
        pm_diags = [d for d in diags if d.rule == "prompt_on_llm_nodes"]
        assert len(pm_diags) == 1
        assert pm_diags[0].severity == Severity.WARNING

    def test_warning_for_box_without_prompt(self):
        g = _graph(
            ("start", "point"),
            ("A", "box"),
            ("exit", "doublecircle"),
            edges=[("start", "A"), ("A", "exit")],
        )
        diags = validate(g)
        pm_diags = [d for d in diags if d.rule == "prompt_on_llm_nodes"]
        assert len(pm_diags) == 1


class TestValidateOrRaise:
    def test_raises_validation_error_on_errors(self):
        g = _graph(("A", "box", {"prompt": "x"}))
        with pytest.raises(ValidationError) as exc_info:
            validate_or_raise(g)
        assert len(exc_info.value.diagnostics) > 0
        assert all(d.severity == Severity.ERROR for d in exc_info.value.diagnostics)

    def test_returns_warnings_without_raising(self):
        g = _graph(
            ("start", "point"),
            ("A", "codergen"),
            ("exit", "doublecircle"),
            edges=[("start", "A"), ("A", "exit")],
        )
        diags = validate_or_raise(g)
        assert all(d.severity != Severity.ERROR for d in diags)
        assert any(d.severity == Severity.WARNING for d in diags)
