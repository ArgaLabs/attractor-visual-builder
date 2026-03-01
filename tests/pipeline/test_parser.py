"""Tests for attractor.pipeline.parser.parse_dot."""

import pytest

from attractor.pipeline.parser import ParseError, parse_dot


class TestSimpleLinear:
    def test_four_nodes_three_edges(self):
        g = parse_dot("digraph { start -> A -> B -> exit }")
        assert len(g.nodes) == 4
        assert len(g.edges) == 3
        assert "start" in g.nodes
        assert "A" in g.nodes
        assert "B" in g.nodes
        assert "exit" in g.nodes

    def test_edge_source_target(self):
        g = parse_dot("digraph { start -> A -> B -> exit }")
        assert g.edges[0].source == "start"
        assert g.edges[0].target == "A"
        assert g.edges[1].source == "A"
        assert g.edges[1].target == "B"
        assert g.edges[2].source == "B"
        assert g.edges[2].target == "exit"


class TestGraphAttributes:
    def test_graph_goal(self):
        g = parse_dot('digraph { graph [goal="test"] start -> exit }')
        assert g.attrs.get("goal") == "test"
        assert g.goal == "test"

    def test_multiple_graph_attrs(self):
        g = parse_dot('digraph { graph [goal="build app", fidelity="full"] start -> exit }')
        assert g.attrs["goal"] == "build app"
        assert g.attrs["fidelity"] == "full"


class TestNodeAttributes:
    def test_shape_and_prompt(self):
        g = parse_dot('digraph { A [shape=box, prompt="do X"] start -> A -> exit }')
        node_a = g.nodes["A"]
        assert node_a.type == "box"
        assert node_a.prompt == "do X"

    def test_timeout_coercion(self):
        g = parse_dot('digraph { A [shape=box, prompt="x", timeout="900s"] start -> A -> exit }')
        node_a = g.nodes["A"]
        assert node_a.timeout == 900.0

    def test_max_retries(self):
        g = parse_dot('digraph { A [shape=box, prompt="x", max_retries="3"] start -> A -> exit }')
        assert g.nodes["A"].max_retries == 3


class TestEdgeAttributes:
    def test_label_and_condition(self):
        g = parse_dot('digraph { A -> B [label="next", condition="outcome=success", weight=1] }')
        assert len(g.edges) == 1
        edge = g.edges[0]
        assert edge.label == "next"
        assert edge.condition == "outcome=success"
        assert edge.weight == 1

    def test_chained_edges_share_attrs(self):
        g = parse_dot('digraph { A -> B -> C [label="x"] }')
        assert len(g.edges) == 2
        assert g.edges[0].label == "x"
        assert g.edges[1].label == "x"


class TestSubgraph:
    def test_flattened_nodes(self):
        dot = """
        digraph {
            subgraph cluster_backend {
                graph [label="backend"]
                node [shape=box]
                X [prompt="do x"]
                Y [prompt="do y"]
            }
            start -> X -> Y -> exit
        }
        """
        g = parse_dot(dot)
        assert "X" in g.nodes
        assert "Y" in g.nodes
        assert g.nodes["X"].type == "box"
        assert g.nodes["Y"].type == "box"

    def test_class_derived_from_cluster_name(self):
        dot = """
        digraph {
            subgraph cluster_frontend {
                Z [prompt="z"]
            }
            start -> Z -> exit
        }
        """
        g = parse_dot(dot)
        assert g.nodes["Z"].css_class == "frontend"

    def test_class_derived_from_graph_label(self):
        dot = """
        digraph {
            subgraph unnamed {
                graph [label="myclass"]
                W [prompt="w"]
            }
            start -> W -> exit
        }
        """
        g = parse_dot(dot)
        assert g.nodes["W"].css_class == "myclass"


class TestComments:
    def test_line_comment_stripped(self):
        dot = """
        digraph {
            // this is a comment
            start -> exit
        }
        """
        g = parse_dot(dot)
        assert len(g.nodes) == 2

    def test_block_comment_stripped(self):
        dot = """
        digraph {
            /* block comment */
            start -> exit
        }
        """
        g = parse_dot(dot)
        assert len(g.nodes) == 2

    def test_inline_comment(self):
        dot = "digraph { start -> exit; // inline\n}"
        g = parse_dot(dot)
        assert len(g.nodes) == 2


class TestRejection:
    def test_undirected_graph_rejected(self):
        with pytest.raises(ParseError, match="Undirected"):
            parse_dot("graph { A -- B }")

    def test_multiple_digraphs_rejected(self):
        with pytest.raises(ParseError, match="Multiple digraph"):
            parse_dot("digraph { start -> exit } digraph { start -> exit }")

    def test_empty_input_rejected(self):
        with pytest.raises(ParseError, match="Empty input"):
            parse_dot("")


class TestQuoting:
    def test_quoted_attribute_value(self):
        g = parse_dot('digraph { A [prompt="hello world"] start -> A -> exit }')
        assert g.nodes["A"].prompt == "hello world"

    def test_unquoted_attribute_value(self):
        g = parse_dot("digraph { A [shape=box] start -> A -> exit }")
        assert g.nodes["A"].type == "box"


class TestSemicolons:
    def test_semicolons_optional(self):
        g1 = parse_dot("digraph { start -> A -> exit }")
        g2 = parse_dot("digraph { start -> A -> exit; }")
        assert len(g1.nodes) == len(g2.nodes)
        assert len(g1.edges) == len(g2.edges)

    def test_semicolons_between_statements(self):
        g = parse_dot("digraph { A [shape=box]; B [shape=box]; A -> B; }")
        assert len(g.nodes) == 2
        assert len(g.edges) == 1


class TestNamedDigraph:
    def test_named_digraph(self):
        g = parse_dot("digraph pipeline { start -> exit }")
        assert len(g.nodes) == 2
