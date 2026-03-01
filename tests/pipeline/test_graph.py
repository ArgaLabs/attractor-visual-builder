"""Tests for attractor.pipeline.graph."""

import pytest

from attractor.pipeline.graph import Edge, Graph, Node, _coerce_value, _parse_duration


class TestCoerceValue:
    def test_true_values(self):
        assert _coerce_value("true") is True
        assert _coerce_value("True") is True
        assert _coerce_value("yes") is True

    def test_false_values(self):
        assert _coerce_value("false") is False
        assert _coerce_value("False") is False
        assert _coerce_value("no") is False

    def test_integer(self):
        assert _coerce_value("42") == 42
        assert isinstance(_coerce_value("42"), int)

    def test_float(self):
        assert _coerce_value("3.14") == pytest.approx(3.14)

    def test_duration_seconds(self):
        assert _coerce_value("10s") == 10.0

    def test_duration_minutes(self):
        assert _coerce_value("5m") == 300.0

    def test_duration_hours(self):
        assert _coerce_value("2h") == 7200.0

    def test_duration_milliseconds(self):
        assert _coerce_value("500ms") == 0.5

    def test_plain_string(self):
        assert _coerce_value("hello") == "hello"


class TestParseDuration:
    def test_seconds(self):
        assert _parse_duration("10s") == 10.0
        assert _parse_duration("10sec") == 10.0

    def test_minutes(self):
        assert _parse_duration("5m") == 300.0
        assert _parse_duration("5min") == 300.0

    def test_hours(self):
        assert _parse_duration("2h") == 7200.0
        assert _parse_duration("2hr") == 7200.0

    def test_milliseconds(self):
        assert _parse_duration("500ms") == 0.5

    def test_no_unit_defaults_seconds(self):
        assert _parse_duration("30") == 30.0

    def test_invalid_returns_none(self):
        assert _parse_duration("abc") is None
        assert _parse_duration("") is None

    def test_decimal(self):
        assert _parse_duration("1.5s") == 1.5


class TestNodeProperties:
    def test_type_from_shape(self):
        n = Node(id="A", attrs={"shape": "box"})
        assert n.type == "box"

    def test_type_default(self):
        n = Node(id="A")
        assert n.type == "codergen"

    def test_label_from_attrs(self):
        n = Node(id="A", attrs={"label": "My Node"})
        assert n.label == "My Node"

    def test_label_fallback_to_id(self):
        n = Node(id="A")
        assert n.label == "A"

    def test_prompt(self):
        n = Node(id="A", attrs={"prompt": "Do something"})
        assert n.prompt == "Do something"

    def test_prompt_empty_default(self):
        n = Node(id="A")
        assert n.prompt == ""

    def test_goal_gate_true(self):
        n = Node(id="A", attrs={"goal_gate": True})
        assert n.goal_gate is True

    def test_goal_gate_string(self):
        n = Node(id="A", attrs={"goal_gate": "yes"})
        assert n.goal_gate is True

    def test_goal_gate_false_default(self):
        n = Node(id="A")
        assert n.goal_gate is False

    def test_max_retries(self):
        n = Node(id="A", attrs={"max_retries": 3})
        assert n.max_retries == 3

    def test_max_retries_default(self):
        n = Node(id="A")
        assert n.max_retries == 0

    def test_timeout_float(self):
        n = Node(id="A", attrs={"timeout": 30.0})
        assert n.timeout == 30.0

    def test_timeout_duration_string(self):
        n = Node(id="A", attrs={"timeout": "5m"})
        assert n.timeout == 300.0

    def test_timeout_none(self):
        n = Node(id="A")
        assert n.timeout is None

    def test_retry_target(self):
        n = Node(id="A", attrs={"retry_target": "B"})
        assert n.retry_target == "B"

    def test_llm_model(self):
        n = Node(id="A", attrs={"llm_model": "gpt-4"})
        assert n.llm_model == "gpt-4"

    def test_fidelity(self):
        n = Node(id="A", attrs={"fidelity": "compact"})
        assert n.fidelity == "compact"


class TestEdgeProperties:
    def test_label(self):
        e = Edge(source="A", target="B", attrs={"label": "next"})
        assert e.label == "next"

    def test_label_default(self):
        e = Edge(source="A", target="B")
        assert e.label == ""

    def test_condition(self):
        e = Edge(source="A", target="B", attrs={"condition": "outcome=success"})
        assert e.condition == "outcome=success"

    def test_condition_default(self):
        e = Edge(source="A", target="B")
        assert e.condition == ""

    def test_weight(self):
        e = Edge(source="A", target="B", attrs={"weight": 5})
        assert e.weight == 5.0

    def test_weight_default(self):
        e = Edge(source="A", target="B")
        assert e.weight == 0.0

    def test_loop_restart(self):
        e = Edge(source="A", target="B", attrs={"loop_restart": True})
        assert e.loop_restart is True

    def test_loop_restart_default(self):
        e = Edge(source="A", target="B")
        assert e.loop_restart is False


class TestGraphMethods:
    def _make_graph(self):
        g = Graph()
        g.add_node(Node(id="start", attrs={"shape": "point"}))
        g.add_node(Node(id="A", attrs={"shape": "box"}))
        g.add_node(Node(id="B", attrs={"shape": "box"}))
        g.add_node(Node(id="exit", attrs={"shape": "doublecircle"}))
        g.add_edge(Edge(source="start", target="A"))
        g.add_edge(Edge(source="A", target="B"))
        g.add_edge(Edge(source="B", target="exit"))
        return g

    def test_outgoing_edges(self):
        g = self._make_graph()
        edges = g.outgoing_edges("A")
        assert len(edges) == 1
        assert edges[0].target == "B"

    def test_incoming_edges(self):
        g = self._make_graph()
        edges = g.incoming_edges("B")
        assert len(edges) == 1
        assert edges[0].source == "A"

    def test_start_nodes(self):
        g = self._make_graph()
        starts = g.start_nodes()
        assert len(starts) == 1
        assert starts[0].id == "start"

    def test_exit_nodes(self):
        g = self._make_graph()
        exits = g.exit_nodes()
        assert len(exits) == 1
        assert exits[0].id == "exit"

    def test_all_node_ids(self):
        g = self._make_graph()
        assert g.all_node_ids() == {"start", "A", "B", "exit"}

    def test_node_lookup(self):
        g = self._make_graph()
        assert g.node("A") is not None
        assert g.node("missing") is None

    def test_goal_from_attrs(self):
        g = Graph(attrs={"goal": "build"})
        assert g.goal == "build"

    def test_goal_empty_default(self):
        g = Graph()
        assert g.goal == ""
