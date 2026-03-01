"""OpenAI adapter using the Responses API (/v1/responses)."""

from __future__ import annotations

import base64
import json
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

from attractor.llm.adapters.base import ProviderAdapter
from attractor.llm.errors import error_from_status_code
from attractor.llm.models import (
    ContentKind,
    ContentPart,
    FinishReason,
    Message,
    Request,
    Response,
    Role,
    StreamEvent,
    StreamEventType,
    ToolCallData,
    ToolDefinition,
    Usage,
)
from attractor.llm.streaming import parse_sse


class OpenAIAdapter(ProviderAdapter):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        org_id: str | None = None,
        project_id: str | None = None,
        default_headers: dict[str, str] | None = None,
        timeout: float = 120.0,
    ):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._base_url = base_url.rstrip("/")
        self._org_id = org_id
        self._project_id = project_id
        self._timeout = timeout
        self._extra_headers = default_headers or {}
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "openai"

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers: dict[str, str] = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                **self._extra_headers,
            }
            if self._org_id:
                headers["OpenAI-Organization"] = self._org_id
            if self._project_id:
                headers["OpenAI-Project"] = self._project_id
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=httpx.Timeout(self._timeout, connect=10.0),
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _build_request_body(self, request: Request) -> dict[str, Any]:
        body: dict[str, Any] = {"model": request.model}

        instructions: list[str] = []
        input_items: list[dict[str, Any]] = []

        for msg in request.messages:
            if msg.role in (Role.SYSTEM, Role.DEVELOPER):
                instructions.append(msg.text)
                continue

            if msg.role == Role.TOOL:
                for part in msg.content:
                    if part.kind == ContentKind.TOOL_RESULT and part.tool_result:
                        content = part.tool_result.content
                        if isinstance(content, dict):
                            content = json.dumps(content)
                        input_items.append(
                            {
                                "type": "function_call_output",
                                "call_id": part.tool_result.tool_call_id,
                                "output": str(content),
                            }
                        )
                continue

            if msg.role == Role.ASSISTANT:
                for part in msg.content:
                    if part.kind == ContentKind.TOOL_CALL and part.tool_call:
                        args = part.tool_call.arguments
                        if isinstance(args, dict):
                            args = json.dumps(args)
                        input_items.append(
                            {
                                "type": "function_call",
                                "id": part.tool_call.id,
                                "name": part.tool_call.name,
                                "arguments": str(args),
                            }
                        )
                    elif part.kind == ContentKind.TEXT and part.text:
                        input_items.append(
                            {
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "output_text", "text": part.text}],
                            }
                        )
                continue

            content_items: list[dict[str, Any]] = []
            for part in msg.content:
                if part.kind == ContentKind.TEXT and part.text is not None:
                    content_items.append({"type": "input_text", "text": part.text})
                elif part.kind == ContentKind.IMAGE and part.image:
                    if part.image.url:
                        content_items.append(
                            {
                                "type": "input_image",
                                "image_url": part.image.url,
                            }
                        )
                    elif part.image.data:
                        mt = part.image.media_type or "image/png"
                        b64 = base64.b64encode(part.image.data).decode()
                        content_items.append(
                            {
                                "type": "input_image",
                                "image_url": f"data:{mt};base64,{b64}",
                            }
                        )

            if content_items:
                input_items.append(
                    {
                        "type": "message",
                        "role": "user",
                        "content": content_items,
                    }
                )

        if instructions:
            body["instructions"] = "\n\n".join(instructions)
        if input_items:
            body["input"] = input_items

        if request.tools:
            body["tools"] = [self._translate_tool(t) for t in request.tools]

        if request.tool_choice:
            body["tool_choice"] = self._translate_tool_choice(request.tool_choice)

        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.top_p is not None:
            body["top_p"] = request.top_p
        if request.max_tokens is not None:
            body["max_output_tokens"] = request.max_tokens

        if request.reasoning_effort:
            body["reasoning"] = {"effort": request.reasoning_effort}

        if request.response_format and request.response_format.type == "json_schema":
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "json_schema": request.response_format.json_schema,
                    "strict": request.response_format.strict,
                }
            }

        opts = (request.provider_options or {}).get("openai", {})
        for k, v in opts.items():
            body[k] = v

        return body

    @staticmethod
    def _translate_tool(tool: ToolDefinition) -> dict[str, Any]:
        return {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }

    @staticmethod
    def _translate_tool_choice(tc: Any) -> Any:
        if tc.mode == "auto":
            return "auto"
        if tc.mode == "none":
            return "none"
        if tc.mode == "required":
            return "required"
        if tc.mode == "named" and tc.tool_name:
            return {"type": "function", "function": {"name": tc.tool_name}}
        return "auto"

    def _parse_response(self, data: dict[str, Any]) -> Response:
        content_parts: list[ContentPart] = []

        for item in data.get("output", []):
            item_type = item.get("type", "")
            if item_type == "message":
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        content_parts.append(ContentPart.text_part(c.get("text", "")))
            elif item_type == "function_call":
                args_str = item.get("arguments", "{}")
                try:
                    args = json.loads(args_str)
                except (json.JSONDecodeError, TypeError):
                    args = args_str
                content_parts.append(
                    ContentPart(
                        kind=ContentKind.TOOL_CALL,
                        tool_call=ToolCallData(
                            id=item.get("id", ""),
                            name=item.get("name", ""),
                            arguments=args,
                        ),
                    )
                )

        has_tool_calls = any(p.kind == ContentKind.TOOL_CALL for p in content_parts)
        status = data.get("status", "completed")
        raw_reason = "stop" if status == "completed" else status
        if has_tool_calls:
            reason = FinishReason.TOOL_CALLS
            raw_reason = "tool_calls"
        elif status == "completed":
            reason = FinishReason.STOP
        elif status == "incomplete":
            reason = FinishReason.LENGTH
        else:
            reason = FinishReason.OTHER

        usage_data = data.get("usage", {})
        reasoning_tokens = None
        if "output_tokens_details" in usage_data:
            reasoning_tokens = usage_data["output_tokens_details"].get("reasoning_tokens")

        return Response(
            id=data.get("id", ""),
            model=data.get("model", ""),
            provider="openai",
            message=Message(role=Role.ASSISTANT, content=content_parts),
            finish_reason=FinishReason(reason=reason, raw=raw_reason),
            usage=Usage(
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
                reasoning_tokens=reasoning_tokens,
                cache_read_tokens=usage_data.get("input_tokens_details", {}).get("cached_tokens"),
                raw=usage_data,
            ),
            raw=data,
        )

    async def complete(self, request: Request) -> Response:
        client = self._get_client()
        body = self._build_request_body(request)
        resp = await client.post("/responses", json=body)
        if resp.status_code != 200:
            self._raise_error(resp)
        return self._parse_response(resp.json())

    async def stream(self, request: Request) -> AsyncIterator[StreamEvent]:
        client = self._get_client()
        body = self._build_request_body(request)
        body["stream"] = True

        async with client.stream("POST", "/responses", json=body) as resp:
            if resp.status_code != 200:
                data = await resp.aread()
                self._raise_error_from_bytes(resp.status_code, data, resp.headers)

            text_started = False
            current_tc: dict[str, str] = {}

            async def _line_iter() -> AsyncIterator[str]:
                async for line in resp.aiter_lines():
                    yield line

            async for sse in parse_sse(_line_iter()):
                if sse.data == "[DONE]":
                    break

                try:
                    ev = json.loads(sse.data)
                except json.JSONDecodeError:
                    continue

                ev_type = ev.get("type", sse.event)

                if "output_text.delta" in ev_type:
                    if not text_started:
                        yield StreamEvent(type=StreamEventType.TEXT_START, text_id="0")
                        text_started = True
                    yield StreamEvent(
                        type=StreamEventType.TEXT_DELTA,
                        delta=ev.get("delta", ""),
                        text_id="0",
                    )

                elif "function_call_arguments.delta" in ev_type:
                    call_id = ev.get("item_id", "")
                    if call_id not in current_tc:
                        current_tc[call_id] = ""
                        from attractor.llm.models import ToolCall

                        yield StreamEvent(
                            type=StreamEventType.TOOL_CALL_START,
                            tool_call=ToolCall(id=call_id, name=ev.get("name", "")),
                        )
                    current_tc[call_id] += ev.get("delta", "")
                    from attractor.llm.models import ToolCall

                    yield StreamEvent(
                        type=StreamEventType.TOOL_CALL_DELTA,
                        tool_call=ToolCall(
                            id=call_id,
                            raw_arguments=ev.get("delta", ""),
                        ),
                    )

                elif "output_item.done" in ev_type:
                    item = ev.get("item", {})
                    if item.get("type") == "function_call":
                        call_id = item.get("id", "")
                        args_str = item.get("arguments", "{}")
                        try:
                            args = json.loads(args_str)
                        except json.JSONDecodeError:
                            args = {}
                        from attractor.llm.models import ToolCall

                        yield StreamEvent(
                            type=StreamEventType.TOOL_CALL_END,
                            tool_call=ToolCall(
                                id=call_id,
                                name=item.get("name", ""),
                                arguments=args,
                            ),
                        )
                    elif item.get("type") == "message" and text_started:
                        yield StreamEvent(type=StreamEventType.TEXT_END, text_id="0")
                        text_started = False

                elif ev_type == "response.completed":
                    resp_data = ev.get("response", {})
                    parsed = self._parse_response(resp_data)
                    yield StreamEvent(
                        type=StreamEventType.FINISH,
                        finish_reason=parsed.finish_reason,
                        usage=parsed.usage,
                        response=parsed,
                    )

    def _raise_error(self, resp: httpx.Response) -> None:
        try:
            body = resp.json()
            message = body.get("error", {}).get("message", resp.text)
            code = body.get("error", {}).get("code")
        except Exception:
            message = resp.text
            code = None
            body = None

        retry_after = resp.headers.get("retry-after")
        ra_float = float(retry_after) if retry_after else None

        raise error_from_status_code(
            status_code=resp.status_code,
            message=message,
            provider="openai",
            error_code=code,
            raw=body,
            retry_after=ra_float,
        )

    def _raise_error_from_bytes(
        self, status_code: int, data: bytes, headers: httpx.Headers
    ) -> None:
        try:
            body = json.loads(data)
            message = body.get("error", {}).get("message", data.decode())
            code = body.get("error", {}).get("code")
        except Exception:
            message = data.decode(errors="replace")
            code = None
            body = None

        retry_after = headers.get("retry-after")
        ra_float = float(retry_after) if retry_after else None

        raise error_from_status_code(
            status_code=status_code,
            message=message,
            provider="openai",
            error_code=code,
            raw=body,
            retry_after=ra_float,
        )
