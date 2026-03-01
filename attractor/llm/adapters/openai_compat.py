"""OpenAI-compatible adapter for third-party endpoints using Chat Completions API."""

from __future__ import annotations

import base64
import json
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
    ToolCall,
    ToolCallData,
    Usage,
)
from attractor.llm.streaming import parse_sse


class OpenAICompatibleAdapter(ProviderAdapter):
    """For vLLM, Ollama, Together AI, Groq, etc."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "http://localhost:8000/v1",
        timeout: float = 120.0,
        provider_name: str = "openai-compatible",
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._provider_name = provider_name
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return self._provider_name

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
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
        messages: list[dict[str, Any]] = []

        for msg in request.messages:
            role_str = msg.role.value
            if msg.role == Role.TOOL:
                for part in msg.content:
                    if part.kind == ContentKind.TOOL_RESULT and part.tool_result:
                        content = part.tool_result.content
                        if isinstance(content, dict):
                            content = json.dumps(content)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": part.tool_result.tool_call_id,
                                "content": str(content),
                            }
                        )
                continue

            content: Any
            has_non_text = any(p.kind != ContentKind.TEXT for p in msg.content)
            if has_non_text:
                content = []
                for part in msg.content:
                    if part.kind == ContentKind.TEXT and part.text:
                        content.append({"type": "text", "text": part.text})
                    elif part.kind == ContentKind.IMAGE and part.image:
                        if part.image.url:
                            content.append(
                                {
                                    "type": "image_url",
                                    "image_url": {"url": part.image.url},
                                }
                            )
                        elif part.image.data:
                            mt = part.image.media_type or "image/png"
                            b64 = base64.b64encode(part.image.data).decode()
                            content.append(
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{mt};base64,{b64}"},
                                }
                            )
            else:
                content = msg.text

            msg_dict: dict[str, Any] = {"role": role_str, "content": content}

            tool_calls = []
            for part in msg.content:
                if part.kind == ContentKind.TOOL_CALL and part.tool_call:
                    args = part.tool_call.arguments
                    if isinstance(args, dict):
                        args = json.dumps(args)
                    tool_calls.append(
                        {
                            "id": part.tool_call.id,
                            "type": "function",
                            "function": {
                                "name": part.tool_call.name,
                                "arguments": str(args),
                            },
                        }
                    )
            if tool_calls:
                msg_dict["tool_calls"] = tool_calls

            messages.append(msg_dict)

        body["messages"] = messages

        if request.tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in request.tools
            ]

        if request.tool_choice:
            tc = request.tool_choice
            if tc.mode in ("auto", "none", "required"):
                body["tool_choice"] = tc.mode
            elif tc.mode == "named" and tc.tool_name:
                body["tool_choice"] = {"type": "function", "function": {"name": tc.tool_name}}

        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.top_p is not None:
            body["top_p"] = request.top_p
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens
        if request.stop_sequences:
            body["stop"] = request.stop_sequences

        return body

    def _parse_response(self, data: dict[str, Any]) -> Response:
        choice = data.get("choices", [{}])[0] if data.get("choices") else {}
        message = choice.get("message", {})
        content_parts: list[ContentPart] = []

        if message.get("content"):
            content_parts.append(ContentPart.text_part(message["content"]))

        for tc in message.get("tool_calls", []):
            fn = tc.get("function", {})
            args_str = fn.get("arguments", "{}")
            try:
                args = json.loads(args_str)
            except (json.JSONDecodeError, TypeError):
                args = args_str
            content_parts.append(
                ContentPart(
                    kind=ContentKind.TOOL_CALL,
                    tool_call=ToolCallData(
                        id=tc.get("id", ""),
                        name=fn.get("name", ""),
                        arguments=args,
                    ),
                )
            )

        raw_reason = choice.get("finish_reason", "stop")
        reason_map = {
            "stop": FinishReason.STOP,
            "length": FinishReason.LENGTH,
            "tool_calls": FinishReason.TOOL_CALLS,
            "content_filter": FinishReason.CONTENT_FILTER,
        }
        unified = reason_map.get(raw_reason or "", FinishReason.OTHER)

        usage_data = data.get("usage", {})
        return Response(
            id=data.get("id", ""),
            model=data.get("model", ""),
            provider=self._provider_name,
            message=Message(role=Role.ASSISTANT, content=content_parts),
            finish_reason=FinishReason(reason=unified, raw=raw_reason),
            usage=Usage(
                input_tokens=usage_data.get("prompt_tokens", 0),
                output_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
                raw=usage_data,
            ),
            raw=data,
        )

    async def complete(self, request: Request) -> Response:
        client = self._get_client()
        body = self._build_request_body(request)
        resp = await client.post("/chat/completions", json=body)
        if resp.status_code != 200:
            self._raise_error(resp)
        return self._parse_response(resp.json())

    async def stream(self, request: Request) -> AsyncIterator[StreamEvent]:
        client = self._get_client()
        body = self._build_request_body(request)
        body["stream"] = True
        body["stream_options"] = {"include_usage": True}

        async with client.stream("POST", "/chat/completions", json=body) as resp:
            if resp.status_code != 200:
                data = await resp.aread()
                self._raise_error_from_bytes(resp.status_code, data)

            text_started = False
            tc_buffers: dict[int, dict[str, str]] = {}

            async def _line_iter() -> AsyncIterator[str]:
                async for line in resp.aiter_lines():
                    yield line

            async for sse in parse_sse(_line_iter()):
                if sse.data == "[DONE]":
                    break

                try:
                    chunk = json.loads(sse.data)
                except json.JSONDecodeError:
                    continue

                choice = chunk.get("choices", [{}])[0] if chunk.get("choices") else {}
                delta = choice.get("delta", {})

                if delta.get("content"):
                    if not text_started:
                        yield StreamEvent(type=StreamEventType.TEXT_START, text_id="0")
                        text_started = True
                    yield StreamEvent(
                        type=StreamEventType.TEXT_DELTA,
                        delta=delta["content"],
                        text_id="0",
                    )

                for tc in delta.get("tool_calls", []):
                    idx = tc.get("index", 0)
                    if idx not in tc_buffers:
                        tc_buffers[idx] = {"id": tc.get("id", ""), "name": "", "arguments": ""}
                        fn = tc.get("function", {})
                        tc_buffers[idx]["name"] = fn.get("name", "")
                        yield StreamEvent(
                            type=StreamEventType.TOOL_CALL_START,
                            tool_call=ToolCall(
                                id=tc_buffers[idx]["id"],
                                name=tc_buffers[idx]["name"],
                            ),
                        )
                    fn = tc.get("function", {})
                    if fn.get("arguments"):
                        tc_buffers[idx]["arguments"] += fn["arguments"]
                        yield StreamEvent(
                            type=StreamEventType.TOOL_CALL_DELTA,
                            tool_call=ToolCall(
                                id=tc_buffers[idx]["id"],
                                raw_arguments=fn["arguments"],
                            ),
                        )

                finish_reason = choice.get("finish_reason")
                if finish_reason:
                    if text_started:
                        yield StreamEvent(type=StreamEventType.TEXT_END, text_id="0")
                    for buf in tc_buffers.values():
                        try:
                            args = json.loads(buf["arguments"]) if buf["arguments"] else {}
                        except json.JSONDecodeError:
                            args = {}
                        yield StreamEvent(
                            type=StreamEventType.TOOL_CALL_END,
                            tool_call=ToolCall(id=buf["id"], name=buf["name"], arguments=args),
                        )

                usage_data = chunk.get("usage")
                if usage_data:
                    reason_map = {
                        "stop": FinishReason.STOP,
                        "length": FinishReason.LENGTH,
                        "tool_calls": FinishReason.TOOL_CALLS,
                    }
                    yield StreamEvent(
                        type=StreamEventType.FINISH,
                        finish_reason=FinishReason(
                            reason=reason_map.get(finish_reason or "", FinishReason.STOP),
                            raw=finish_reason,
                        ),
                        usage=Usage(
                            input_tokens=usage_data.get("prompt_tokens", 0),
                            output_tokens=usage_data.get("completion_tokens", 0),
                            total_tokens=usage_data.get("total_tokens", 0),
                        ),
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

        raise error_from_status_code(
            status_code=resp.status_code,
            message=message,
            provider=self._provider_name,
            error_code=code,
            raw=body,
        )

    def _raise_error_from_bytes(self, status_code: int, data: bytes) -> None:
        try:
            body = json.loads(data)
            message = body.get("error", {}).get("message", data.decode())
        except Exception:
            message = data.decode(errors="replace")
            body = None

        raise error_from_status_code(
            status_code=status_code,
            message=message,
            provider=self._provider_name,
            raw=body,
        )
