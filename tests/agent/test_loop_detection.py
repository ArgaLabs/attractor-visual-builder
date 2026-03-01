"""Tests for attractor.agent.loop_detection."""

from __future__ import annotations

from attractor.agent.loop_detection import detect_loop, tool_call_signature


class TestToolCallSignature:
    def test_consistent_hash(self):
        sig1 = tool_call_signature("read_file", {"file_path": "/a.py"})
        sig2 = tool_call_signature("read_file", {"file_path": "/a.py"})
        assert sig1 == sig2

    def test_different_args_different_hash(self):
        sig1 = tool_call_signature("read_file", {"file_path": "/a.py"})
        sig2 = tool_call_signature("read_file", {"file_path": "/b.py"})
        assert sig1 != sig2

    def test_different_name_different_hash(self):
        sig1 = tool_call_signature("read_file", {"file_path": "/a.py"})
        sig2 = tool_call_signature("write_file", {"file_path": "/a.py"})
        assert sig1 != sig2

    def test_format_contains_name_and_hex(self):
        sig = tool_call_signature("shell", {"command": "ls"})
        assert sig.startswith("shell:")
        assert len(sig.split(":")[1]) == 8

    def test_key_order_does_not_matter(self):
        sig1 = tool_call_signature("edit", {"a": 1, "b": 2})
        sig2 = tool_call_signature("edit", {"b": 2, "a": 1})
        assert sig1 == sig2


class TestDetectLoop:
    def test_returns_false_when_signatures_below_window_size(self):
        sigs = ["a:00000001"] * 5
        assert detect_loop(sigs, window_size=10) is False

    def test_returns_true_for_repeating_pattern_length_1(self):
        sig = tool_call_signature("read_file", {"file_path": "/x"})
        sigs = [sig] * 10
        assert detect_loop(sigs, window_size=10) is True

    def test_returns_true_for_repeating_pattern_length_2(self):
        sig_a = tool_call_signature("read_file", {"file_path": "/a"})
        sig_b = tool_call_signature("write_file", {"file_path": "/b", "content": ""})
        sigs = [sig_a, sig_b] * 5
        assert detect_loop(sigs, window_size=10) is True

    def test_returns_false_for_diverse_signatures(self):
        sigs = [tool_call_signature("tool", {"i": i}) for i in range(10)]
        assert detect_loop(sigs, window_size=10) is False

    def test_returns_true_for_pattern_length_3(self):
        a = tool_call_signature("t", {"x": 1})
        b = tool_call_signature("t", {"x": 2})
        c = tool_call_signature("t", {"x": 3})
        # window_size=9 is divisible by 3
        sigs = [a, b, c] * 3
        assert detect_loop(sigs, window_size=9) is True

    def test_long_history_only_checks_recent_window(self):
        diverse = [tool_call_signature("t", {"i": i}) for i in range(20)]
        same = [tool_call_signature("read_file", {"file_path": "/x"})] * 10
        sigs = diverse + same
        assert detect_loop(sigs, window_size=10) is True

    def test_almost_repeating_not_detected(self):
        sig = tool_call_signature("read_file", {"file_path": "/x"})
        diff = tool_call_signature("read_file", {"file_path": "/y"})
        sigs = [sig] * 9 + [diff]
        assert detect_loop(sigs, window_size=10) is False
