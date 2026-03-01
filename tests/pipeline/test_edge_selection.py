"""Tests for attractor.pipeline.edge_selection.select_edge."""

from attractor.pipeline.edge_selection import select_edge
from attractor.pipeline.graph import Edge
from attractor.pipeline.outcome import Outcome, StageStatus


def _edge(src: str, tgt: str, **attrs) -> Edge:
    return Edge(source=src, target=tgt, attrs=attrs)


class TestConditionMatching:
    def test_condition_matching_wins(self):
        edges = [
            _edge("A", "B", condition="outcome=success"),
            _edge("A", "C", condition="outcome=fail"),
        ]
        outcome = Outcome(status=StageStatus.SUCCESS)
        result = select_edge(edges, outcome)
        assert result is not None
        assert result.target == "B"


class TestPreferredLabel:
    def test_preferred_label_match(self):
        edges = [
            _edge("A", "B", label="approve"),
            _edge("A", "C", label="reject"),
        ]
        outcome = Outcome(status=StageStatus.SUCCESS, preferred_label="reject")
        result = select_edge(edges, outcome)
        assert result is not None
        assert result.target == "C"


class TestSuggestedNextIds:
    def test_suggested_next_ids_match(self):
        edges = [
            _edge("A", "B"),
            _edge("A", "C"),
        ]
        outcome = Outcome(status=StageStatus.SUCCESS, suggested_next_ids=["C"])
        result = select_edge(edges, outcome)
        assert result is not None
        assert result.target == "C"


class TestHighestWeight:
    def test_highest_weight_wins(self):
        edges = [
            _edge("A", "B", weight=1),
            _edge("A", "C", weight=10),
            _edge("A", "D", weight=5),
        ]
        outcome = Outcome(status=StageStatus.SUCCESS)
        result = select_edge(edges, outcome)
        assert result is not None
        assert result.target == "C"


class TestLexicalTiebreak:
    def test_lexical_tiebreak(self):
        edges = [
            _edge("A", "Z"),
            _edge("A", "B"),
            _edge("A", "M"),
        ]
        outcome = Outcome(status=StageStatus.SUCCESS)
        result = select_edge(edges, outcome)
        assert result is not None
        assert result.target == "B"


class TestNoEdges:
    def test_no_outgoing_edges(self):
        result = select_edge([], Outcome(status=StageStatus.SUCCESS))
        assert result is None


class TestCombinedPriority:
    def test_condition_beats_label(self):
        edges = [
            _edge("A", "B", condition="outcome=success"),
            _edge("A", "C", label="preferred"),
        ]
        outcome = Outcome(status=StageStatus.SUCCESS, preferred_label="preferred")
        result = select_edge(edges, outcome)
        assert result is not None
        assert result.target == "B"

    def test_label_beats_suggested(self):
        edges = [
            _edge("A", "B", label="pick_me"),
            _edge("A", "C"),
        ]
        outcome = Outcome(
            status=StageStatus.SUCCESS,
            preferred_label="pick_me",
            suggested_next_ids=["C"],
        )
        result = select_edge(edges, outcome)
        assert result is not None
        assert result.target == "B"

    def test_suggested_beats_weight(self):
        edges = [
            _edge("A", "B", weight=100),
            _edge("A", "C", weight=1),
        ]
        outcome = Outcome(status=StageStatus.SUCCESS, suggested_next_ids=["C"])
        result = select_edge(edges, outcome)
        assert result is not None
        assert result.target == "C"

    def test_weight_beats_lexical(self):
        edges = [
            _edge("A", "B", weight=1),
            _edge("A", "A_first", weight=10),
        ]
        outcome = Outcome(status=StageStatus.SUCCESS)
        result = select_edge(edges, outcome)
        assert result is not None
        assert result.target == "A_first"

    def test_unconditional_fallback_when_no_condition_matches(self):
        edges = [
            _edge("A", "B", condition="outcome=fail"),
            _edge("A", "C"),
        ]
        outcome = Outcome(status=StageStatus.SUCCESS)
        result = select_edge(edges, outcome)
        assert result is not None
        assert result.target == "C"
