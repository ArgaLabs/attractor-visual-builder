"""Tests for attractor.pipeline.fidelity."""

from attractor.pipeline.fidelity import is_valid_fidelity, resolve_fidelity


class TestIsValidFidelity:
    def test_known_modes(self):
        assert is_valid_fidelity("full") is True
        assert is_valid_fidelity("truncate") is True
        assert is_valid_fidelity("compact") is True

    def test_summary_prefix(self):
        assert is_valid_fidelity("summary:latest") is True
        assert is_valid_fidelity("summary:") is True

    def test_invalid_mode(self):
        assert is_valid_fidelity("bogus") is False
        assert is_valid_fidelity("") is False
        assert is_valid_fidelity("FULL") is False


class TestResolveFidelity:
    def test_edge_takes_precedence(self):
        assert resolve_fidelity("compact", "full", "truncate") == "compact"

    def test_node_when_no_edge(self):
        assert resolve_fidelity(None, "truncate", "full") == "truncate"

    def test_graph_when_no_edge_or_node(self):
        assert resolve_fidelity(None, None, "compact") == "compact"

    def test_default_when_all_none(self):
        assert resolve_fidelity(None, None, None) == "full"

    def test_custom_default(self):
        assert resolve_fidelity(None, None, None, default="compact") == "compact"

    def test_skips_invalid(self):
        assert resolve_fidelity("bogus", None, "full") == "full"

    def test_skips_invalid_node(self):
        assert resolve_fidelity(None, "invalid", "compact") == "compact"
