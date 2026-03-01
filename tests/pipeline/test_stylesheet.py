"""Tests for attractor.pipeline.stylesheet."""

from attractor.pipeline.graph import Graph, Node
from attractor.pipeline.stylesheet import apply_stylesheet, parse_stylesheet


class TestParseUniversal:
    def test_universal_rule(self):
        ss = parse_stylesheet("* { llm_model: foo; }")
        assert len(ss.rules) == 1
        assert ss.rules[0].selector == "*"
        assert ss.rules[0].selector_type == "universal"
        assert ss.rules[0].properties == {"llm_model": "foo"}
        assert ss.rules[0].specificity == 0


class TestParseClass:
    def test_class_rule(self):
        ss = parse_stylesheet(".backend { llm_model: gpt-4; }")
        assert len(ss.rules) == 1
        assert ss.rules[0].selector == ".backend"
        assert ss.rules[0].selector_type == "class"
        assert ss.rules[0].specificity == 1


class TestParseId:
    def test_id_rule(self):
        ss = parse_stylesheet("#nodeA { llm_model: claude; }")
        assert len(ss.rules) == 1
        assert ss.rules[0].selector == "#nodeA"
        assert ss.rules[0].selector_type == "id"
        assert ss.rules[0].specificity == 2


class TestSpecificityOrder:
    def test_id_beats_class_beats_universal(self):
        ss = parse_stylesheet("""
            * { llm_model: default; }
            .backend { llm_model: class_model; }
            #special { llm_model: id_model; }
        """)
        sorted_rules = sorted(ss.rules, key=lambda r: r.specificity)
        assert sorted_rules[0].selector_type == "universal"
        assert sorted_rules[1].selector_type == "class"
        assert sorted_rules[2].selector_type == "id"


class TestApplyStylesheet:
    def test_universal_applies_to_all(self):
        ss = parse_stylesheet("* { llm_model: default_model; }")
        g = Graph()
        g.add_node(Node(id="A", attrs={"shape": "box"}))
        g.add_node(Node(id="B", attrs={"shape": "box"}))
        apply_stylesheet(g, ss)
        assert g.nodes["A"].attrs["llm_model"] == "default_model"
        assert g.nodes["B"].attrs["llm_model"] == "default_model"

    def test_class_applies_to_matching(self):
        ss = parse_stylesheet(".backend { llm_model: gpt-4; }")
        g = Graph()
        g.add_node(Node(id="A", attrs={"shape": "box"}, css_class="backend"))
        g.add_node(Node(id="B", attrs={"shape": "box"}, css_class="frontend"))
        apply_stylesheet(g, ss)
        assert g.nodes["A"].attrs.get("llm_model") == "gpt-4"
        assert "llm_model" not in g.nodes["B"].attrs

    def test_id_applies_to_matching_node(self):
        ss = parse_stylesheet("#A { llm_model: special; }")
        g = Graph()
        g.add_node(Node(id="A", attrs={"shape": "box"}))
        g.add_node(Node(id="B", attrs={"shape": "box"}))
        apply_stylesheet(g, ss)
        assert g.nodes["A"].attrs["llm_model"] == "special"
        assert "llm_model" not in g.nodes["B"].attrs


class TestExplicitOverride:
    def test_explicit_node_attrs_override_stylesheet(self):
        ss = parse_stylesheet("* { llm_model: default; }")
        g = Graph()
        g.add_node(Node(id="A", attrs={"shape": "box", "llm_model": "explicit"}))
        apply_stylesheet(g, ss)
        assert g.nodes["A"].attrs["llm_model"] == "explicit"


class TestMultipleProperties:
    def test_multiple_properties_parsed(self):
        ss = parse_stylesheet("* { llm_model: foo; fidelity: compact; }")
        assert ss.rules[0].properties == {"llm_model": "foo", "fidelity": "compact"}


class TestEmptyStylesheet:
    def test_empty_string(self):
        ss = parse_stylesheet("")
        assert len(ss.rules) == 0

    def test_whitespace_only(self):
        ss = parse_stylesheet("   ")
        assert len(ss.rules) == 0
