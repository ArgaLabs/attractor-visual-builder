"""SSE parser and stream accumulator."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from attractor.llm.models import (
    ContentKind,
    ContentPart,
    FinishReason,
    Message,
    Response,
    Role,
    StreamEvent,
    StreamEventType,
    ToolCallData,
    Usage,
)


class SSEEvent:
    """A single Server-Sent Event."""

    def __init__(self, event: str = "message", data: str = "", retry: int | None = None):
        self.event = event
        self.data = data
        self.retry = retry


async def parse_sse(lines: AsyncIterator[str]) -> AsyncIterator[SSEEvent]:
    """Parse an SSE stream from an async line iterator."""
    event_type = "message"
    data_lines: list[str] = []
    retry_val: int | None = None

    async for raw_line in lines:
        line = raw_line.rstrip("\n").rstrip("\r")

        if line.startswith(":"):
            continue

        if line == "":
            if data_lines:
                data = "\n".join(data_lines)
                yield SSEEvent(event=event_type, data=data, retry=retry_val)
                event_type = "message"
                data_lines = []
                retry_val = None
            continue

        if ":" in line:
            field, _, value = line.partition(":")
            if value.startswith(" "):
                value = value[1:]
        else:
            field = line
            value = ""

        if field == "event":
            event_type = value
        elif field == "data":
            data_lines.append(value)
        elif field == "retry":
            try:
                retry_val = int(value)
            except ValueError:
                pass

    if data_lines:
        yield SSEEvent(event=event_type, data="\n".join(data_lines), retry=retry_val)


class StreamAccumulator:
    """Collects StreamEvents into a complete Response."""

    def __init__(self) -> None:
        self._text_parts: dict[str, str] = {}
        self._reasoning_parts: list[str] = []
        self._tool_calls: dict[str, dict[str, Any]] = {}
        self._finish_reason: FinishReason = FinishReason()
        self._usage: Usage = Usage()
        self._response_id: str = ""
        self._model: str = ""
        self._provider: str = ""
        self._raw: dict[str, Any] | None = None

    def process(self, event: StreamEvent) -> None:
        if event.type == StreamEventType.TEXT_DELTA:
            tid = event.text_id or "default"
            self._text_parts.setdefault(tid, "")
            if event.delta:
                self._text_parts[tid] += event.delta

        elif event.type == StreamEventType.REASONING_DELTA:
            if event.reasoning_delta:
                self._reasoning_parts.append(event.reasoning_delta)

        elif event.type == StreamEventType.TOOL_CALL_START:
            if event.tool_call:
                self._tool_calls[event.tool_call.id] = {
                    "id": event.tool_call.id,
                    "name": event.tool_call.name,
                    "arguments": "",
                }

        elif event.type == StreamEventType.TOOL_CALL_DELTA:
            if event.tool_call and event.tool_call.id in self._tool_calls:
                raw = event.tool_call.raw_arguments or ""
                self._tool_calls[event.tool_call.id]["arguments"] += raw

        elif event.type == StreamEventType.TOOL_CALL_END:
            if event.tool_call and event.tool_call.id in self._tool_calls:
                tc = self._tool_calls[event.tool_call.id]
                tc["name"] = event.tool_call.name or tc["name"]
                if event.tool_call.arguments:
                    tc["arguments"] = json.dumps(event.tool_call.arguments)

        elif event.type == StreamEventType.FINISH:
            if event.finish_reason:
                self._finish_reason = event.finish_reason
            if event.usage:
                self._usage = event.usage
            if event.response:
                self._response_id = event.response.id
                self._model = event.response.model
                self._provider = event.response.provider
                self._raw = event.response.raw

    def response(self) -> Response:
        content_parts: list[ContentPart] = []

        full_text = "".join(self._text_parts.values())
        if full_text:
            content_parts.append(ContentPart.text_part(full_text))

        reasoning_text = "".join(self._reasoning_parts)
        if reasoning_text:
            content_parts.append(ContentPart.thinking_part(reasoning_text))

        for tc in self._tool_calls.values():
            args_str = tc.get("arguments", "")
            try:
                args = json.loads(args_str) if args_str else {}
            except json.JSONDecodeError:
                args = args_str
            content_parts.append(
                ContentPart(
                    kind=ContentKind.TOOL_CALL,
                    tool_call=ToolCallData(
                        id=tc["id"],
                        name=tc["name"],
                        arguments=args,
                    ),
                )
            )

        message = Message(role=Role.ASSISTANT, content=content_parts)
        return Response(
            id=self._response_id or "accumulated",
            model=self._model,
            provider=self._provider,
            message=message,
            finish_reason=self._finish_reason,
            usage=self._usage,
            raw=self._raw,
        )
