"""Tests for attractor.llm.generate."""

from __future__ import annotations

import json
from typing import Any

import pytest

from attractor.llm.client import Client
from attractor.llm.errors import NoObjectGeneratedError
from attractor.llm.generate import generate, generate_object
from attractor.llm.models import (
    ContentKind,
    ContentPart,
    FinishReason,
    Message,
    Request,
    Response,
    Role,
    ToolCallData,
    Usage,
)
from attractor.llm.tools import Tool
from tests.conftest import FakeAdapter


def _text_response(text: str, provider: str = "fake") -> Response:
    return Response(
        model="fake-model",
        provider=provider,
        message=Message(
            role=Role.ASSISTANT,
            content=[ContentPart.text_part(text)],
        ),
        finish_reason=FinishReason(reason=FinishReason.STOP),
        usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15),
    )


def _tool_call_response(tool_id: str, tool_name: str, arguments: dict[str, Any]) -> Response:
    return Response(
        model="fake-model",
        provider="fake",
        message=Message(
            role=Role.ASSISTANT,
            content=[
                ContentPart(
                    kind=ContentKind.TOOL_CALL,
                    tool_call=ToolCallData(
                        id=tool_id,
                        name=tool_name,
                        arguments=arguments,
                    ),
                )
            ],
        ),
        finish_reason=FinishReason(reason=FinishReason.TOOL_CALLS),
        usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15),
    )


def _make_client(responses: list[Response]) -> tuple[Client, FakeAdapter]:
    adapter = FakeAdapter()
    call_count = 0

    async def _dynamic_complete(request: Request) -> Response:
        nonlocal call_count
        resp = responses[min(call_count, len(responses) - 1)]
        call_count += 1
        adapter._requests.append(request)
        return resp

    adapter.complete = _dynamic_complete
    client = Client(providers={"fake": adapter}, default_provider="fake")
    return client, adapter


# ---------------------------------------------------------------------------
# generate() – no tools
# ---------------------------------------------------------------------------


class TestGenerateNoTools:
    async def test_returns_text(self):
        client, _ = _make_client([_text_response("Hello world")])
        result = await generate(
            model="fake-model",
            prompt="Say hello",
            client=client,
            max_retries=0,
        )
        assert result.text == "Hello world"
        assert result.finish_reason.reason == FinishReason.STOP
        assert len(result.steps) == 1

    async def test_system_prompt_included(self):
        client, adapter = _make_client([_text_response("ok")])
        await generate(
            model="fake-model",
            prompt="test",
            system="Be helpful",
            client=client,
            max_retries=0,
        )
        request = adapter._requests[0]
        assert request.messages[0].role == Role.SYSTEM
        assert request.messages[0].text == "Be helpful"

    async def test_messages_param(self):
        client, adapter = _make_client([_text_response("ok")])
        msgs = [Message.user("hi"), Message.assistant("hello"), Message.user("bye")]
        await generate(
            model="fake-model",
            messages=msgs,
            client=client,
            max_retries=0,
        )
        request = adapter._requests[0]
        assert len(request.messages) == 3

    async def test_prompt_and_messages_raises(self):
        client, _ = _make_client([_text_response("ok")])
        with pytest.raises(ValueError, match="not both"):
            await generate(
                model="fake-model",
                prompt="hello",
                messages=[Message.user("hi")],
                client=client,
            )

    async def test_usage_tracked(self):
        client, _ = _make_client([_text_response("ok")])
        result = await generate(
            model="fake-model",
            prompt="test",
            client=client,
            max_retries=0,
        )
        assert result.usage.input_tokens == 10
        assert result.usage.output_tokens == 5
        assert result.total_usage.total_tokens == 15


# ---------------------------------------------------------------------------
# generate() – with tools
# ---------------------------------------------------------------------------


class TestGenerateWithTools:
    async def test_tool_loop_executes(self):
        tool_resp = _tool_call_response("tc1", "add", {"a": 2, "b": 3})
        final_resp = _text_response("The answer is 5")
        client, _ = _make_client([tool_resp, final_resp])

        add_tool = Tool(
            name="add",
            description="Add two numbers",
            parameters={
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
            },
            execute=lambda a, b: str(a + b),
        )
        result = await generate(
            model="fake-model",
            prompt="What is 2+3?",
            tools=[add_tool],
            max_tool_rounds=1,
            client=client,
            max_retries=0,
        )
        assert result.text == "The answer is 5"
        assert len(result.steps) == 2
        assert result.steps[0].tool_calls[0].name == "add"
        assert result.steps[0].tool_results[0].content == "5"

    async def test_max_tool_rounds_stops_loop(self):
        tool_resp = _tool_call_response("tc1", "loop_tool", {})
        client, adapter = _make_client([tool_resp, tool_resp, tool_resp])

        loop_tool = Tool(
            name="loop_tool",
            description="Always called",
            execute=lambda: "result",
        )
        result = await generate(
            model="fake-model",
            prompt="run",
            tools=[loop_tool],
            max_tool_rounds=1,
            client=client,
            max_retries=0,
        )
        assert len(result.steps) == 2
        assert len(adapter._requests) == 2

    async def test_tool_error_returned_as_error_result(self):
        tool_resp = _tool_call_response("tc1", "failing", {})
        final_resp = _text_response("Tool failed")
        client, _ = _make_client([tool_resp, final_resp])

        failing_tool = Tool(
            name="failing",
            description="Always fails",
            execute=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        result = await generate(
            model="fake-model",
            prompt="run",
            tools=[failing_tool],
            max_tool_rounds=1,
            client=client,
            max_retries=0,
        )
        assert result.steps[0].tool_results[0].is_error is True
        assert "boom" in result.steps[0].tool_results[0].content

    async def test_unknown_tool_returns_error(self):
        tool_resp = _tool_call_response("tc1", "nonexistent", {})
        final_resp = _text_response("Sorry")
        client, _ = _make_client([tool_resp, final_resp])

        result = await generate(
            model="fake-model",
            prompt="run",
            tools=[],
            max_tool_rounds=1,
            client=client,
            max_retries=0,
        )
        assert result.steps[0].tool_results[0].is_error is True
        assert "Unknown tool" in result.steps[0].tool_results[0].content

    async def test_async_tool_execution(self):
        tool_resp = _tool_call_response("tc1", "async_tool", {"x": 42})
        final_resp = _text_response("done")
        client, _ = _make_client([tool_resp, final_resp])

        async def async_exec(x):
            return f"async result: {x}"

        async_tool = Tool(
            name="async_tool",
            description="Async tool",
            parameters={"type": "object", "properties": {"x": {"type": "number"}}},
            execute=async_exec,
        )
        result = await generate(
            model="fake-model",
            prompt="run",
            tools=[async_tool],
            max_tool_rounds=1,
            client=client,
            max_retries=0,
        )
        assert result.steps[0].tool_results[0].content == "async result: 42"

    async def test_total_usage_accumulates(self):
        tool_resp = _tool_call_response("tc1", "noop", {})
        final_resp = _text_response("done")
        client, _ = _make_client([tool_resp, final_resp])

        noop_tool = Tool(name="noop", execute=lambda: "ok")
        result = await generate(
            model="fake-model",
            prompt="run",
            tools=[noop_tool],
            max_tool_rounds=1,
            client=client,
            max_retries=0,
        )
        assert result.total_usage.input_tokens == 20
        assert result.total_usage.output_tokens == 10


# ---------------------------------------------------------------------------
# generate_object()
# ---------------------------------------------------------------------------


class TestGenerateObject:
    async def test_parses_json_response(self):
        obj = {"name": "Alice", "age": 30}
        client, _ = _make_client([_text_response(json.dumps(obj))])

        result = await generate_object(
            model="fake-model",
            prompt="Generate a person",
            schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
            },
            client=client,
            max_retries=0,
        )
        assert result.output == obj
        assert result.output["name"] == "Alice"
        assert result.output["age"] == 30

    async def test_invalid_json_raises_no_object_error(self):
        client, _ = _make_client([_text_response("not valid json")])
        with pytest.raises(NoObjectGeneratedError, match="Failed to parse"):
            await generate_object(
                model="fake-model",
                prompt="Generate something",
                client=client,
                max_retries=0,
            )

    async def test_schema_sets_response_format(self):
        client, adapter = _make_client([_text_response('{"x": 1}')])
        await generate_object(
            model="fake-model",
            prompt="test",
            schema={"type": "object", "properties": {"x": {"type": "integer"}}},
            client=client,
            max_retries=0,
        )
        request = adapter._requests[0]
        assert request.response_format is not None
        assert request.response_format.type == "json_schema"
        assert request.response_format.strict is True

    async def test_no_schema_still_parses(self):
        client, _ = _make_client([_text_response('{"key": "value"}')])
        result = await generate_object(
            model="fake-model",
            prompt="return json",
            client=client,
            max_retries=0,
        )
        assert result.output == {"key": "value"}
