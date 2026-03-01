"""Tests for attractor.llm.streaming."""

from __future__ import annotations

from collections.abc import AsyncIterator

from attractor.llm.models import (
    FinishReason,
    StreamEvent,
    StreamEventType,
    ToolCall,
    Usage,
)
from attractor.llm.streaming import StreamAccumulator, parse_sse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _lines(text: str) -> AsyncIterator[str]:
    for line in text.split("\n"):
        yield line


# ---------------------------------------------------------------------------
# parse_sse
# ---------------------------------------------------------------------------


class TestParseSSE:
    async def test_single_line_data(self):
        raw = "data: hello\n\n"
        events = [e async for e in parse_sse(_lines(raw))]
        assert len(events) == 1
        assert events[0].data == "hello"
        assert events[0].event == "message"

    async def test_multi_line_data_joined(self):
        raw = "data: line1\ndata: line2\ndata: line3\n\n"
        events = [e async for e in parse_sse(_lines(raw))]
        assert len(events) == 1
        assert events[0].data == "line1\nline2\nline3"

    async def test_comment_lines_ignored(self):
        raw = ": this is a comment\ndata: actual\n\n"
        events = [e async for e in parse_sse(_lines(raw))]
        assert len(events) == 1
        assert events[0].data == "actual"

    async def test_event_type_parsed(self):
        raw = "event: custom_event\ndata: payload\n\n"
        events = [e async for e in parse_sse(_lines(raw))]
        assert len(events) == 1
        assert events[0].event == "custom_event"
        assert events[0].data == "payload"

    async def test_done_signal(self):
        raw = "data: [DONE]\n\n"
        events = [e async for e in parse_sse(_lines(raw))]
        assert len(events) == 1
        assert events[0].data == "[DONE]"

    async def test_multiple_events(self):
        raw = "data: first\n\ndata: second\n\n"
        events = [e async for e in parse_sse(_lines(raw))]
        assert len(events) == 2
        assert events[0].data == "first"
        assert events[1].data == "second"

    async def test_event_type_resets_between_events(self):
        raw = "event: start\ndata: a\n\ndata: b\n\n"
        events = [e async for e in parse_sse(_lines(raw))]
        assert events[0].event == "start"
        assert events[1].event == "message"

    async def test_retry_field_parsed(self):
        raw = "retry: 3000\ndata: reconnect\n\n"
        events = [e async for e in parse_sse(_lines(raw))]
        assert events[0].retry == 3000

    async def test_data_without_trailing_blank_flushed_at_end(self):
        raw = "data: no trailing blank"
        events = [e async for e in parse_sse(_lines(raw))]
        assert len(events) == 1
        assert events[0].data == "no trailing blank"

    async def test_empty_stream(self):
        raw = ""
        events = [e async for e in parse_sse(_lines(raw))]
        assert len(events) == 0

    async def test_space_after_colon_stripped(self):
        raw = "data: with space\n\n"
        events = [e async for e in parse_sse(_lines(raw))]
        assert events[0].data == "with space"

    async def test_no_space_after_colon(self):
        raw = "data:no space\n\n"
        events = [e async for e in parse_sse(_lines(raw))]
        assert events[0].data == "no space"


# ---------------------------------------------------------------------------
# StreamAccumulator – text deltas
# ---------------------------------------------------------------------------


class TestStreamAccumulatorText:
    def test_text_deltas_produce_complete_text(self):
        acc = StreamAccumulator()
        acc.process(StreamEvent(type=StreamEventType.TEXT_DELTA, delta="Hello "))
        acc.process(StreamEvent(type=StreamEventType.TEXT_DELTA, delta="world"))
        acc.process(
            StreamEvent(
                type=StreamEventType.FINISH,
                finish_reason=FinishReason(reason=FinishReason.STOP),
                usage=Usage(input_tokens=5, output_tokens=2, total_tokens=7),
            )
        )
        resp = acc.response()
        assert resp.text == "Hello world"
        assert resp.finish_reason.reason == "stop"
        assert resp.usage.total_tokens == 7

    def test_empty_deltas_ignored(self):
        acc = StreamAccumulator()
        acc.process(StreamEvent(type=StreamEventType.TEXT_DELTA, delta=None))
        acc.process(StreamEvent(type=StreamEventType.TEXT_DELTA, delta="ok"))
        resp = acc.response()
        assert resp.text == "ok"

    def test_multiple_text_ids_concatenated(self):
        acc = StreamAccumulator()
        acc.process(StreamEvent(type=StreamEventType.TEXT_DELTA, delta="a", text_id="t1"))
        acc.process(StreamEvent(type=StreamEventType.TEXT_DELTA, delta="b", text_id="t2"))
        resp = acc.response()
        assert resp.text == "ab"


# ---------------------------------------------------------------------------
# StreamAccumulator – tool call deltas
# ---------------------------------------------------------------------------


class TestStreamAccumulatorToolCalls:
    def test_tool_call_deltas_produce_complete_call(self):
        acc = StreamAccumulator()
        acc.process(
            StreamEvent(
                type=StreamEventType.TOOL_CALL_START,
                tool_call=ToolCall(id="tc1", name="search"),
            )
        )
        acc.process(
            StreamEvent(
                type=StreamEventType.TOOL_CALL_DELTA,
                tool_call=ToolCall(id="tc1", raw_arguments='{"q":'),
            )
        )
        acc.process(
            StreamEvent(
                type=StreamEventType.TOOL_CALL_DELTA,
                tool_call=ToolCall(id="tc1", raw_arguments=' "test"}'),
            )
        )
        acc.process(
            StreamEvent(
                type=StreamEventType.TOOL_CALL_END,
                tool_call=ToolCall(id="tc1", name="search"),
            )
        )
        acc.process(StreamEvent(type=StreamEventType.FINISH))

        resp = acc.response()
        calls = resp.tool_calls
        assert len(calls) == 1
        assert calls[0].name == "search"
        assert calls[0].arguments == {"q": "test"}

    def test_multiple_tool_calls(self):
        acc = StreamAccumulator()
        acc.process(
            StreamEvent(
                type=StreamEventType.TOOL_CALL_START,
                tool_call=ToolCall(id="tc1", name="read"),
            )
        )
        acc.process(
            StreamEvent(
                type=StreamEventType.TOOL_CALL_DELTA,
                tool_call=ToolCall(id="tc1", raw_arguments='{"path": "/a"}'),
            )
        )
        acc.process(
            StreamEvent(
                type=StreamEventType.TOOL_CALL_END,
                tool_call=ToolCall(id="tc1", name="read"),
            )
        )
        acc.process(
            StreamEvent(
                type=StreamEventType.TOOL_CALL_START,
                tool_call=ToolCall(id="tc2", name="write"),
            )
        )
        acc.process(
            StreamEvent(
                type=StreamEventType.TOOL_CALL_DELTA,
                tool_call=ToolCall(id="tc2", raw_arguments='{"path": "/b"}'),
            )
        )
        acc.process(
            StreamEvent(
                type=StreamEventType.TOOL_CALL_END,
                tool_call=ToolCall(id="tc2", name="write"),
            )
        )
        acc.process(StreamEvent(type=StreamEventType.FINISH))

        resp = acc.response()
        calls = resp.tool_calls
        assert len(calls) == 2
        assert calls[0].name == "read"
        assert calls[1].name == "write"

    def test_text_and_tool_calls_combined(self):
        acc = StreamAccumulator()
        acc.process(StreamEvent(type=StreamEventType.TEXT_DELTA, delta="Let me "))
        acc.process(StreamEvent(type=StreamEventType.TEXT_DELTA, delta="search."))
        acc.process(
            StreamEvent(
                type=StreamEventType.TOOL_CALL_START,
                tool_call=ToolCall(id="tc1", name="search"),
            )
        )
        acc.process(
            StreamEvent(
                type=StreamEventType.TOOL_CALL_DELTA,
                tool_call=ToolCall(id="tc1", raw_arguments="{}"),
            )
        )
        acc.process(
            StreamEvent(
                type=StreamEventType.TOOL_CALL_END,
                tool_call=ToolCall(id="tc1", name="search"),
            )
        )
        acc.process(StreamEvent(type=StreamEventType.FINISH))

        resp = acc.response()
        assert resp.text == "Let me search."
        assert len(resp.tool_calls) == 1
