"""Tests for attractor.llm.models."""

from __future__ import annotations

from attractor.llm.models import (
    ContentKind,
    ContentPart,
    FinishReason,
    Message,
    Response,
    Role,
    StreamEvent,
    StreamEventType,
    ToolCall,
    ToolCallData,
    Usage,
)

# ---------------------------------------------------------------------------
# Message factory methods
# ---------------------------------------------------------------------------


class TestMessageFactories:
    def test_system_creates_system_role(self):
        msg = Message.system("You are helpful.")
        assert msg.role == Role.SYSTEM
        assert len(msg.content) == 1
        assert msg.content[0].kind == ContentKind.TEXT
        assert msg.content[0].text == "You are helpful."

    def test_user_creates_user_role(self):
        msg = Message.user("Hello")
        assert msg.role == Role.USER
        assert msg.content[0].text == "Hello"

    def test_assistant_creates_assistant_role(self):
        msg = Message.assistant("Hi there")
        assert msg.role == Role.ASSISTANT
        assert msg.content[0].text == "Hi there"

    def test_tool_result_creates_tool_role(self):
        msg = Message.tool_result("call_123", "result data")
        assert msg.role == Role.TOOL
        assert msg.tool_call_id == "call_123"
        assert len(msg.content) == 1
        part = msg.content[0]
        assert part.kind == ContentKind.TOOL_RESULT
        assert part.tool_result is not None
        assert part.tool_result.tool_call_id == "call_123"
        assert part.tool_result.content == "result data"
        assert part.tool_result.is_error is False

    def test_tool_result_with_error_flag(self):
        msg = Message.tool_result("call_456", "error!", is_error=True)
        assert msg.content[0].tool_result.is_error is True

    def test_tool_result_with_dict_content(self):
        msg = Message.tool_result("call_789", {"key": "value"})
        assert msg.content[0].tool_result.content == {"key": "value"}


# ---------------------------------------------------------------------------
# Message.text property
# ---------------------------------------------------------------------------


class TestMessageText:
    def test_text_concatenates_text_parts(self):
        msg = Message(
            role=Role.ASSISTANT,
            content=[
                ContentPart.text_part("Hello "),
                ContentPart.text_part("world"),
            ],
        )
        assert msg.text == "Hello world"

    def test_text_ignores_non_text_parts(self):
        msg = Message(
            role=Role.ASSISTANT,
            content=[
                ContentPart.text_part("Hello"),
                ContentPart.tool_call_part("tc1", "fn", {}),
                ContentPart.text_part(" world"),
            ],
        )
        assert msg.text == "Hello world"

    def test_text_empty_when_no_text_parts(self):
        msg = Message(
            role=Role.ASSISTANT,
            content=[ContentPart.tool_call_part("tc1", "fn", {})],
        )
        assert msg.text == ""

    def test_text_empty_for_no_content(self):
        msg = Message(role=Role.ASSISTANT, content=[])
        assert msg.text == ""


# ---------------------------------------------------------------------------
# Usage addition
# ---------------------------------------------------------------------------


class TestUsageAddition:
    def test_basic_addition(self):
        a = Usage(input_tokens=10, output_tokens=5, total_tokens=15)
        b = Usage(input_tokens=20, output_tokens=10, total_tokens=30)
        c = a + b
        assert c.input_tokens == 30
        assert c.output_tokens == 15
        assert c.total_tokens == 45

    def test_none_plus_none_stays_none(self):
        a = Usage(reasoning_tokens=None, cache_read_tokens=None)
        b = Usage(reasoning_tokens=None, cache_read_tokens=None)
        c = a + b
        assert c.reasoning_tokens is None
        assert c.cache_read_tokens is None

    def test_none_plus_value_returns_value(self):
        a = Usage(reasoning_tokens=None)
        b = Usage(reasoning_tokens=100)
        c = a + b
        assert c.reasoning_tokens == 100

    def test_value_plus_none_returns_value(self):
        a = Usage(reasoning_tokens=50)
        b = Usage(reasoning_tokens=None)
        c = a + b
        assert c.reasoning_tokens == 50

    def test_value_plus_value_sums(self):
        a = Usage(cache_read_tokens=10, cache_write_tokens=20)
        b = Usage(cache_read_tokens=30, cache_write_tokens=40)
        c = a + b
        assert c.cache_read_tokens == 40
        assert c.cache_write_tokens == 60


# ---------------------------------------------------------------------------
# ContentPart tagged union
# ---------------------------------------------------------------------------


class TestContentPart:
    def test_text_part(self):
        part = ContentPart.text_part("hello")
        assert part.kind == ContentKind.TEXT
        assert part.text == "hello"
        assert part.image is None
        assert part.tool_call is None

    def test_image_part(self):
        part = ContentPart.image_part(url="https://img.png", detail="high")
        assert part.kind == ContentKind.IMAGE
        assert part.image is not None
        assert part.image.url == "https://img.png"
        assert part.image.detail == "high"
        assert part.text is None

    def test_tool_call_part(self):
        part = ContentPart.tool_call_part("tc1", "my_func", {"x": 1})
        assert part.kind == ContentKind.TOOL_CALL
        assert part.tool_call is not None
        assert part.tool_call.id == "tc1"
        assert part.tool_call.name == "my_func"
        assert part.tool_call.arguments == {"x": 1}

    def test_tool_result_part(self):
        part = ContentPart.tool_result_part("tc1", "output", is_error=False)
        assert part.kind == ContentKind.TOOL_RESULT
        assert part.tool_result is not None
        assert part.tool_result.tool_call_id == "tc1"
        assert part.tool_result.content == "output"

    def test_thinking_part_normal(self):
        part = ContentPart.thinking_part("reasoning here", signature="sig123")
        assert part.kind == ContentKind.THINKING
        assert part.thinking is not None
        assert part.thinking.text == "reasoning here"
        assert part.thinking.signature == "sig123"
        assert part.thinking.redacted is False

    def test_thinking_part_redacted(self):
        part = ContentPart.thinking_part("", redacted=True)
        assert part.kind == ContentKind.REDACTED_THINKING
        assert part.thinking.redacted is True


# ---------------------------------------------------------------------------
# FinishReason
# ---------------------------------------------------------------------------


class TestFinishReason:
    def test_default_reason_is_stop(self):
        fr = FinishReason()
        assert fr.reason == "stop"

    def test_constants_available(self):
        assert FinishReason.STOP == "stop"
        assert FinishReason.LENGTH == "length"
        assert FinishReason.TOOL_CALLS == "tool_calls"
        assert FinishReason.CONTENT_FILTER == "content_filter"
        assert FinishReason.ERROR == "error"
        assert FinishReason.OTHER == "other"

    def test_custom_reason_with_raw(self):
        fr = FinishReason(reason="tool_calls", raw="tool_use")
        assert fr.reason == "tool_calls"
        assert fr.raw == "tool_use"


# ---------------------------------------------------------------------------
# StreamEvent types cover StreamEventType values
# ---------------------------------------------------------------------------


class TestStreamEvent:
    def test_all_event_types_can_be_instantiated(self):
        for evt_type in StreamEventType:
            event = StreamEvent(type=evt_type)
            assert event.type == evt_type

    def test_text_delta_event(self):
        event = StreamEvent(type=StreamEventType.TEXT_DELTA, delta="chunk")
        assert event.delta == "chunk"
        assert event.type == StreamEventType.TEXT_DELTA

    def test_finish_event_with_usage(self):
        usage = Usage(input_tokens=5, output_tokens=3, total_tokens=8)
        event = StreamEvent(
            type=StreamEventType.FINISH,
            finish_reason=FinishReason(reason=FinishReason.STOP),
            usage=usage,
        )
        assert event.usage.total_tokens == 8
        assert event.finish_reason.reason == "stop"

    def test_tool_call_start_event(self):
        tc = ToolCall(id="tc1", name="search", arguments={"q": "test"})
        event = StreamEvent(type=StreamEventType.TOOL_CALL_START, tool_call=tc)
        assert event.tool_call.name == "search"

    def test_timestamp_auto_populated(self):
        event = StreamEvent(type=StreamEventType.STREAM_START)
        assert event.timestamp > 0


# ---------------------------------------------------------------------------
# Response.tool_calls property
# ---------------------------------------------------------------------------


class TestResponseToolCalls:
    def test_extracts_tool_calls_from_content(self):
        msg = Message(
            role=Role.ASSISTANT,
            content=[
                ContentPart.text_part("I'll search for that."),
                ContentPart.tool_call_part("tc1", "search", {"query": "test"}),
            ],
        )
        resp = Response(message=msg)
        calls = resp.tool_calls
        assert len(calls) == 1
        assert calls[0].name == "search"
        assert calls[0].arguments == {"query": "test"}

    def test_tool_call_with_string_arguments(self):
        msg = Message(
            role=Role.ASSISTANT,
            content=[
                ContentPart(
                    kind=ContentKind.TOOL_CALL,
                    tool_call=ToolCallData(id="tc2", name="calc", arguments='{"x": 42}'),
                ),
            ],
        )
        resp = Response(message=msg)
        calls = resp.tool_calls
        assert len(calls) == 1
        assert calls[0].arguments == {"x": 42}
        assert calls[0].raw_arguments == '{"x": 42}'

    def test_response_text_property(self):
        resp = Response(
            message=Message(
                role=Role.ASSISTANT,
                content=[ContentPart.text_part("hello")],
            )
        )
        assert resp.text == "hello"

    def test_response_reasoning_property(self):
        resp = Response(
            message=Message(
                role=Role.ASSISTANT,
                content=[
                    ContentPart.thinking_part("step 1"),
                    ContentPart.text_part("answer"),
                ],
            )
        )
        assert resp.reasoning == "step 1"
