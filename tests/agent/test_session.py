"""Tests for attractor.agent.session.Session with a mock LLM client."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from attractor.agent.config import SessionConfig
from attractor.agent.events import EventKind, SessionEvent
from attractor.agent.execution.local import LocalExecutionEnvironment
from attractor.agent.profiles.anthropic import AnthropicProfile
from attractor.agent.session import Session
from attractor.llm.adapters.base import ProviderAdapter
from attractor.llm.client import Client
from attractor.llm.models import (
    ContentPart,
    FinishReason,
    Message,
    Request,
    Response,
    Role,
    StreamEvent,
    Usage,
)


class FakeAdapter(ProviderAdapter):
    """A fake adapter that returns a sequence of canned responses."""

    def __init__(self, responses: list[Response]):
        self._responses = list(responses)
        self._call_index = 0

    @property
    def name(self) -> str:
        return "fake"

    async def complete(self, request: Request) -> Response:
        if self._call_index < len(self._responses):
            resp = self._responses[self._call_index]
            self._call_index += 1
            return resp
        return Response(
            message=Message.assistant("(no more canned responses)"),
            finish_reason=FinishReason(reason="stop"),
        )

    async def stream(self, request: Request) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError

        yield  # type: ignore[misc]


def _text_response(text: str) -> Response:
    return Response(
        message=Message.assistant(text),
        finish_reason=FinishReason(reason="stop"),
        usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15),
    )


def _tool_call_response(tool_name: str, tool_call_id: str, arguments: dict[str, Any]) -> Response:
    msg = Message(
        role=Role.ASSISTANT,
        content=[ContentPart.tool_call_part(id=tool_call_id, name=tool_name, arguments=arguments)],
    )
    return Response(
        message=msg,
        finish_reason=FinishReason(reason=FinishReason.TOOL_CALLS),
        usage=Usage(input_tokens=20, output_tokens=10, total_tokens=30),
    )


def _make_session(
    responses: list[Response],
    tmp_path,
    config: SessionConfig | None = None,
) -> Session:
    adapter = FakeAdapter(responses)
    client = Client(providers={"anthropic": adapter}, default_provider="anthropic")
    env = LocalExecutionEnvironment(working_dir=str(tmp_path))
    profile = AnthropicProfile()
    return Session(client=client, profile=profile, environment=env, config=config)


class TestProcessInput:
    async def test_sends_user_message_and_gets_response(self, tmp_path):
        session = _make_session([_text_response("Hello!")], tmp_path)
        result = await session.process_input("Hi")
        assert result.text == "Hello!"
        assert result.finish_reason == "stop"
        assert result.usage is not None

    async def test_conversation_grows(self, tmp_path):
        session = _make_session(
            [_text_response("First"), _text_response("Second")],
            tmp_path,
        )
        await session.process_input("one")
        await session.process_input("two")
        conv = session.conversation
        # system + user + assistant + user + assistant
        user_msgs = [m for m in conv if m.role == Role.USER]
        assert len(user_msgs) == 2


class TestToolCallExecution:
    async def test_tool_calls_executed_and_fed_back(self, tmp_path):
        target = tmp_path / "hello.txt"
        target.write_text("hello world\n")

        responses = [
            _tool_call_response("read_file", "tc_1", {"file_path": str(target)}),
            _text_response("I read the file."),
        ]
        session = _make_session(responses, tmp_path)
        result = await session.process_input("Read hello.txt")

        assert result.text == "I read the file."
        assert result.tool_calls_made == 1

        conv = session.conversation
        tool_msgs = [m for m in conv if m.role == Role.TOOL]
        assert len(tool_msgs) == 1
        tool_content = tool_msgs[0].content[0].tool_result.content
        assert "hello world" in tool_content

    async def test_multiple_tool_rounds(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_text("content\n")

        responses = [
            _tool_call_response("read_file", "tc_1", {"file_path": str(f)}),
            _tool_call_response("shell", "tc_2", {"command": "echo done"}),
            _text_response("All done."),
        ]
        session = _make_session(responses, tmp_path)
        result = await session.process_input("Process data")
        assert result.tool_calls_made == 2


class TestTurnLimit:
    async def test_turn_limit_respected(self, tmp_path):
        f = tmp_path / "x.txt"
        f.write_text("x\n")

        responses = [
            _tool_call_response("read_file", f"tc_{i}", {"file_path": str(f)}) for i in range(10)
        ]
        config = SessionConfig(max_tool_rounds_per_input=2)
        session = _make_session(responses, tmp_path, config=config)
        result = await session.process_input("loop")
        assert result.tool_calls_made <= 2


class TestEventsEmitted:
    async def test_session_start_emitted(self, tmp_path):
        events: list[SessionEvent] = []
        session = _make_session([_text_response("ok")], tmp_path)
        session.events.on(lambda e: events.append(e))

        await session.process_input("test")

        kinds = [e.kind for e in events]
        assert EventKind.SESSION_START in kinds

    async def test_user_input_emitted(self, tmp_path):
        events: list[SessionEvent] = []
        session = _make_session([_text_response("ok")], tmp_path)
        session.events.on(lambda e: events.append(e))

        await session.process_input("my input")

        user_events = [e for e in events if e.kind == EventKind.USER_INPUT]
        assert len(user_events) == 1
        assert user_events[0].data.get("text") == "my input"

    async def test_assistant_text_events_emitted(self, tmp_path):
        events: list[SessionEvent] = []
        session = _make_session([_text_response("response text")], tmp_path)
        session.events.on(lambda e: events.append(e))

        await session.process_input("go")

        kinds = [e.kind for e in events]
        assert EventKind.ASSISTANT_TEXT_START in kinds
        assert EventKind.ASSISTANT_TEXT_DELTA in kinds
        assert EventKind.ASSISTANT_TEXT_END in kinds

    async def test_tool_call_events_emitted(self, tmp_path):
        f = tmp_path / "t.txt"
        f.write_text("data\n")

        events: list[SessionEvent] = []
        responses = [
            _tool_call_response("read_file", "tc_x", {"file_path": str(f)}),
            _text_response("done"),
        ]
        session = _make_session(responses, tmp_path)
        session.events.on(lambda e: events.append(e))

        await session.process_input("read")

        kinds = [e.kind for e in events]
        assert EventKind.TOOL_CALL_START in kinds
        assert EventKind.TOOL_CALL_END in kinds

    async def test_turn_limit_event(self, tmp_path):
        f = tmp_path / "t.txt"
        f.write_text("x\n")

        events: list[SessionEvent] = []
        responses = [
            _tool_call_response("read_file", f"tc_{i}", {"file_path": str(f)}) for i in range(10)
        ]
        config = SessionConfig(max_tool_rounds_per_input=1)
        session = _make_session(responses, tmp_path, config=config)
        session.events.on(lambda e: events.append(e))

        await session.process_input("go")

        kinds = [e.kind for e in events]
        assert EventKind.TURN_LIMIT in kinds
