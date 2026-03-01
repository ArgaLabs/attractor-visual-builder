"""Tests for attractor.pipeline.transforms."""

from attractor.pipeline.graph import Graph, Node
from attractor.pipeline.transforms import stylesheet_transform, variable_expansion


class TestVariableExpansion:
    def test_replaces_goal(self):
        g = Graph(attrs={"goal": "build a CLI"})
        g.add_node(Node(id="A", attrs={"prompt": "Please $goal"}))
        variable_expansion(g)
        assert g.nodes["A"].attrs["prompt"] == "Please build a CLI"

    def test_replaces_braced_goal(self):
        g = Graph(attrs={"goal": "deploy"})
        g.add_node(Node(id="A", attrs={"prompt": "Run ${goal} now"}))
        variable_expansion(g)
        assert g.nodes["A"].attrs["prompt"] == "Run deploy now"

    def test_replaces_custom_graph_attr(self):
        g = Graph(attrs={"goal": "test", "version": "2.0"})
        g.add_node(Node(id="A", attrs={"prompt": "ver=$version, goal=$goal"}))
        variable_expansion(g)
        assert "ver=2.0" in g.nodes["A"].attrs["prompt"]
        assert "goal=test" in g.nodes["A"].attrs["prompt"]

    def test_no_replacement_when_no_vars(self):
        g = Graph(attrs={"goal": "x"})
        g.add_node(Node(id="A", attrs={"prompt": "plain text"}))
        variable_expansion(g)
        assert g.nodes["A"].attrs["prompt"] == "plain text"


class TestStylesheetTransform:
    def test_applies_model_override(self):
        g = Graph(attrs={"stylesheet": "* { llm_model: gpt-4o; }"})
        g.add_node(Node(id="A", attrs={"shape": "box"}))
        g.add_node(Node(id="B", attrs={"shape": "box"}))
        stylesheet_transform(g)
        assert g.nodes["A"].attrs["llm_model"] == "gpt-4o"
        assert g.nodes["B"].attrs["llm_model"] == "gpt-4o"

    def test_no_stylesheet_is_noop(self):
        g = Graph()
        g.add_node(Node(id="A", attrs={"shape": "box"}))
        stylesheet_transform(g)
        assert "llm_model" not in g.nodes["A"].attrs

    def test_explicit_attrs_not_overridden(self):
        g = Graph(attrs={"stylesheet": "* { llm_model: default; }"})
        g.add_node(Node(id="A", attrs={"shape": "box", "llm_model": "claude"}))
        stylesheet_transform(g)
        assert g.nodes["A"].attrs["llm_model"] == "claude"
