"""High-level generation API: generate(), stream(), generate_object()."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from pydantic import BaseModel, Field

from attractor.llm.client import Client, get_default_client
from attractor.llm.errors import NoObjectGeneratedError
from attractor.llm.models import (
    FinishReason,
    Message,
    Request,
    Response,
    ResponseFormat,
    StreamEvent,
    StreamEventType,
    ToolCall,
    ToolChoice,
    ToolDefinition,
    ToolResult,
    Usage,
    Warning,
)
from attractor.llm.retry import RetryPolicy, retry_async
from attractor.llm.streaming import StreamAccumulator
from attractor.llm.tools import Tool


class StepResult(BaseModel):
    text: str = ""
    reasoning: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    finish_reason: FinishReason = Field(default_factory=FinishReason)
    usage: Usage = Field(default_factory=Usage)
    response: Response = Field(default_factory=Response)
    warnings: list[Warning] = Field(default_factory=list)


class GenerateResult(BaseModel):
    text: str = ""
    reasoning: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    finish_reason: FinishReason = Field(default_factory=FinishReason)
    usage: Usage = Field(default_factory=Usage)
    total_usage: Usage = Field(default_factory=Usage)
    steps: list[StepResult] = Field(default_factory=list)
    response: Response = Field(default_factory=Response)
    output: Any = None


StopCondition = Callable[[list[StepResult]], bool]


async def generate(
    model: str,
    prompt: str | None = None,
    messages: list[Message] | None = None,
    system: str | None = None,
    tools: list[Tool] | None = None,
    tool_choice: ToolChoice | None = None,
    max_tool_rounds: int = 1,
    stop_when: StopCondition | None = None,
    response_format: ResponseFormat | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    max_tokens: int | None = None,
    stop_sequences: list[str] | None = None,
    reasoning_effort: str | None = None,
    provider: str | None = None,
    provider_options: dict[str, Any] | None = None,
    max_retries: int = 2,
    client: Client | None = None,
) -> GenerateResult:
    if prompt and messages:
        raise ValueError("Provide either 'prompt' or 'messages', not both")

    cli = client or get_default_client()
    conversation: list[Message] = []

    if system:
        conversation.append(Message.system(system))
    if messages:
        conversation.extend(messages)
    elif prompt:
        conversation.append(Message.user(prompt))

    tool_defs: list[ToolDefinition] | None = None
    tool_map: dict[str, Tool] = {}
    if tools:
        tool_defs = [t.to_definition() for t in tools]
        tool_map = {t.name: t for t in tools}

    steps: list[StepResult] = []
    total_usage = Usage()
    retry_policy = RetryPolicy(max_retries=max_retries)

    for round_num in range(max_tool_rounds + 1):
        request = Request(
            model=model,
            messages=list(conversation),
            provider=provider,
            tools=tool_defs,
            tool_choice=tool_choice,
            response_format=response_format,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stop_sequences=stop_sequences,
            reasoning_effort=reasoning_effort,
            provider_options=provider_options,
        )

        response = await retry_async(cli.complete, retry_policy, request)

        step_tool_calls = response.tool_calls
        step_tool_results: list[ToolResult] = []

        if step_tool_calls and response.finish_reason.reason == FinishReason.TOOL_CALLS:
            step_tool_results = await _execute_tools(tool_map, step_tool_calls)

        step = StepResult(
            text=response.text,
            reasoning=response.reasoning,
            tool_calls=step_tool_calls,
            tool_results=step_tool_results,
            finish_reason=response.finish_reason,
            usage=response.usage,
            response=response,
            warnings=response.warnings,
        )
        steps.append(step)
        total_usage = total_usage + response.usage

        if not step_tool_calls or response.finish_reason.reason != FinishReason.TOOL_CALLS:
            break
        if round_num >= max_tool_rounds:
            break
        if stop_when and stop_when(steps):
            break

        conversation.append(response.message)
        for result in step_tool_results:
            conversation.append(
                Message.tool_result(
                    tool_call_id=result.tool_call_id,
                    content=result.content,
                    is_error=result.is_error,
                )
            )

    final = steps[-1] if steps else StepResult()
    return GenerateResult(
        text=final.text,
        reasoning=final.reasoning,
        tool_calls=final.tool_calls,
        tool_results=final.tool_results,
        finish_reason=final.finish_reason,
        usage=final.usage,
        total_usage=total_usage,
        steps=steps,
        response=final.response,
    )


async def _execute_tools(tool_map: dict[str, Tool], tool_calls: list[ToolCall]) -> list[ToolResult]:
    async def _exec_one(tc: ToolCall) -> ToolResult:
        tool = tool_map.get(tc.name)
        if not tool or not tool.execute:
            return ToolResult(
                tool_call_id=tc.id,
                content=f"Unknown tool: {tc.name}",
                is_error=True,
            )
        try:
            result = tool.execute(**tc.arguments)
            if asyncio.iscoroutine(result):
                result = await result
            content = result if isinstance(result, (str, dict, list)) else str(result)
            return ToolResult(tool_call_id=tc.id, content=content)
        except Exception as e:
            return ToolResult(
                tool_call_id=tc.id,
                content=f"Tool error ({tc.name}): {e}",
                is_error=True,
            )

    results = await asyncio.gather(*[_exec_one(tc) for tc in tool_calls])
    return list(results)


async def generate_object(
    model: str,
    prompt: str | None = None,
    messages: list[Message] | None = None,
    system: str | None = None,
    schema: dict[str, Any] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    reasoning_effort: str | None = None,
    provider: str | None = None,
    provider_options: dict[str, Any] | None = None,
    max_retries: int = 2,
    client: Client | None = None,
) -> GenerateResult:
    rf = None
    if schema:
        rf = ResponseFormat(type="json_schema", json_schema=schema, strict=True)

    result = await generate(
        model=model,
        prompt=prompt,
        messages=messages,
        system=system,
        response_format=rf,
        temperature=temperature,
        max_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
        provider=provider,
        provider_options=provider_options,
        max_retries=max_retries,
        max_tool_rounds=0,
        client=client,
    )

    try:
        result.output = json.loads(result.text)
    except (json.JSONDecodeError, TypeError) as e:
        raise NoObjectGeneratedError(f"Failed to parse structured output: {e}") from e

    return result


class StreamResult:
    def __init__(self, event_iter: AsyncIterator[StreamEvent]):
        self._iter = event_iter
        self._accumulator = StreamAccumulator()
        self._done = False

    def __aiter__(self) -> AsyncIterator[StreamEvent]:
        return self._consume()

    async def _consume(self) -> AsyncIterator[StreamEvent]:
        async for event in self._iter:
            self._accumulator.process(event)
            yield event
            if event.type == StreamEventType.FINISH:
                self._done = True

    def response(self) -> Response:
        return self._accumulator.response()

    @property
    def partial_response(self) -> Response:
        return self._accumulator.response()


async def stream_generate(
    model: str,
    prompt: str | None = None,
    messages: list[Message] | None = None,
    system: str | None = None,
    tools: list[Tool] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    reasoning_effort: str | None = None,
    provider: str | None = None,
    provider_options: dict[str, Any] | None = None,
    client: Client | None = None,
) -> StreamResult:
    if prompt and messages:
        raise ValueError("Provide either 'prompt' or 'messages', not both")

    cli = client or get_default_client()
    conversation: list[Message] = []

    if system:
        conversation.append(Message.system(system))
    if messages:
        conversation.extend(messages)
    elif prompt:
        conversation.append(Message.user(prompt))

    tool_defs: list[ToolDefinition] | None = None
    if tools:
        tool_defs = [t.to_definition() for t in tools]

    request = Request(
        model=model,
        messages=conversation,
        provider=provider,
        tools=tool_defs,
        temperature=temperature,
        max_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
        provider_options=provider_options,
    )

    event_iter = await cli.stream(request)
    return StreamResult(event_iter)
