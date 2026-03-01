"""Tests for attractor.agent.truncation."""

from __future__ import annotations

from attractor.agent.truncation import (
    DEFAULT_CHAR_LIMITS,
    DEFAULT_LINE_LIMITS,
    DEFAULT_TRUNCATION_MODES,
    truncate_lines,
    truncate_output,
    truncate_tool_output,
)


class TestTruncateOutput:
    def test_under_limit_returned_unchanged(self):
        text = "hello world"
        assert truncate_output(text, max_chars=100) == text

    def test_exact_limit_returned_unchanged(self):
        text = "a" * 50
        assert truncate_output(text, max_chars=50) == text

    def test_head_tail_splits_with_marker(self):
        text = "A" * 40 + "B" * 40
        result = truncate_output(text, max_chars=40, mode="head_tail")

        half = 40 // 2
        assert result.startswith("A" * half)
        assert result.endswith("B" * half)
        assert "[WARNING: Tool output was truncated." in result
        assert "40 characters were removed from the middle." in result

    def test_head_tail_preserves_total_content_chars(self):
        text = "x" * 1000
        result = truncate_output(text, max_chars=200, mode="head_tail")
        assert result[:100] == "x" * 100
        assert result[-100:] == "x" * 100

    def test_tail_mode_keeps_last_n_chars(self):
        text = "A" * 50 + "B" * 50
        result = truncate_output(text, max_chars=50, mode="tail")

        assert result.endswith("B" * 50)
        assert "[WARNING: Tool output was truncated." in result
        assert "First 50 characters were removed." in result

    def test_unknown_mode_truncates_from_start(self):
        text = "A" * 30 + "B" * 30
        result = truncate_output(text, max_chars=30, mode="unknown")
        assert result == "A" * 30


class TestTruncateLines:
    def test_under_limit_returned_unchanged(self):
        text = "line1\nline2\nline3"
        assert truncate_lines(text, max_lines=10) == text

    def test_exact_limit_returned_unchanged(self):
        text = "\n".join(f"line{i}" for i in range(5))
        assert truncate_lines(text, max_lines=5) == text

    def test_over_limit_head_tail_with_marker(self):
        lines = [f"line{i}" for i in range(20)]
        text = "\n".join(lines)
        result = truncate_lines(text, max_lines=6)

        head_count = 3
        tail_count = 3
        omitted = 20 - head_count - tail_count

        assert result.startswith("line0\nline1\nline2")
        assert f"[... {omitted} lines omitted ...]" in result
        assert result.endswith("line17\nline18\nline19")

    def test_odd_limit_splits_correctly(self):
        lines = [f"L{i}" for i in range(10)]
        text = "\n".join(lines)
        result = truncate_lines(text, max_lines=3)

        # head_count = 1, tail_count = 2
        assert result.startswith("L0\n")
        assert "[... 7 lines omitted ...]" in result
        assert result.endswith("L8\nL9")


class TestTruncateToolOutput:
    def test_uses_correct_defaults_per_tool(self):
        for tool_name, char_limit in DEFAULT_CHAR_LIMITS.items():
            short_output = "x" * (char_limit - 1)
            assert truncate_tool_output(short_output, tool_name) == short_output

    def test_read_file_uses_head_tail_mode(self):
        assert DEFAULT_TRUNCATION_MODES["read_file"] == "head_tail"
        text = "A" * 100000
        result = truncate_tool_output(text, "read_file")
        assert "removed from the middle" in result

    def test_grep_uses_tail_mode(self):
        assert DEFAULT_TRUNCATION_MODES["grep"] == "tail"
        text = "A" * 50000
        result = truncate_tool_output(text, "grep")
        assert "First" in result

    def test_custom_char_limits(self):
        result = truncate_tool_output(
            "x" * 200,
            "read_file",
            char_limits={"read_file": 50},
        )
        assert "[WARNING" in result

    def test_char_truncation_before_line_truncation(self):
        long_line = "x" * 100
        text = "\n".join([long_line] * 500)
        result = truncate_tool_output(text, "shell")

        # shell: char_limit=30000, line_limit=256
        # First char truncation runs, then line truncation
        # After char truncation + line truncation, total lines
        # should be constrained by the line limit (256) plus any
        # marker lines injected
        has_char_warning = "[WARNING" in result
        has_line_omit = "[..." in result and "lines omitted" in result
        assert has_char_warning or has_line_omit

    def test_unknown_tool_gets_default_30k_limit(self):
        text = "y" * 40000
        result = truncate_tool_output(text, "unknown_tool")
        assert "[WARNING" in result

    def test_tool_with_no_line_limit_skips_line_truncation(self):
        assert DEFAULT_LINE_LIMITS.get("read_file") is None
        many_short_lines = "\n".join(f"L{i}" for i in range(10))
        result = truncate_tool_output(many_short_lines, "read_file")
        assert result == many_short_lines
