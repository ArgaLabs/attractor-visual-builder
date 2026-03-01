"""Anthropic adapter using the Messages API (/v1/messages)."""

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
    ThinkingData,
    ToolCall,
    ToolCallData,
    ToolDefinition,
    Usage,
)
from attractor.llm.streaming import parse_sse


class AnthropicAdapter(ProviderAdapter):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.anthropic.com",
        timeout: float = 120.0,
        default_headers: dict[str, str] | None = None,
    ):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._extra_headers = default_headers or {}
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "anthropic"

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers: dict[str, str] = {
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
                **self._extra_headers,
            }
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

    def supports_tool_choice(self, mode: str) -> bool:
        return mode != "none"

    def _build_request_body(self, request: Request) -> tuple[dict[str, Any], dict[str, str]]:
        body: dict[str, Any] = {"model": request.model}
        extra_headers: dict[str, str] = {}

        system_parts: list[str] = []
        messages: list[dict[str, Any]] = []

        for msg in request.messages:
            if msg.role in (Role.SYSTEM, Role.DEVELOPER):
                system_parts.append(msg.text)
                continue
            translated = self._translate_message(msg)
            if translated:
                if messages and messages[-1]["role"] == translated["role"]:
                    messages[-1]["content"].extend(translated["content"])
                else:
                    messages.append(translated)

        if system_parts:
            system_text = "\n\n".join(system_parts)
            body["system"] = [
                {"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}
            ]

        body["messages"] = messages
        body["max_tokens"] = request.max_tokens or 4096

        if request.tools:
            body["tools"] = [self._translate_tool(t) for t in request.tools]
            if body["tools"]:
                body["tools"][-1]["cache_control"] = {"type": "ephemeral"}

        if request.tool_choice:
            tc = request.tool_choice
            if tc.mode == "auto":
                body["tool_choice"] = {"type": "auto"}
            elif tc.mode == "required":
                body["tool_choice"] = {"type": "any"}
            elif tc.mode == "named" and tc.tool_name:
                body["tool_choice"] = {"type": "tool", "name": tc.tool_name}
            elif tc.mode == "none":
                body.pop("tools", None)

        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.top_p is not None:
            body["top_p"] = request.top_p
        if request.stop_sequences:
            body["stop_sequences"] = request.stop_sequences

        opts = (request.provider_options or {}).get("anthropic", {})
        beta_headers: list[str] = ["prompt-caching-2024-07-31"]

        if "thinking" in opts:
            body["thinking"] = opts["thinking"]
            beta_headers.append("interleaved-thinking-2025-05-14")
        if "beta_headers" in opts:
            beta_headers.extend(opts["beta_headers"])

        if request.reasoning_effort:
            effort_map = {"low": 5000, "medium": 20000, "high": 50000}
            budget = effort_map.get(request.reasoning_effort, 20000)
            if "thinking" not in body:
                body["thinking"] = {"type": "enabled", "budget_tokens": budget}
                beta_headers.append("interleaved-thinking-2025-05-14")

        if beta_headers:
            extra_headers["anthropic-beta"] = ",".join(sorted(set(beta_headers)))

        for k, v in opts.items():
            if k not in ("thinking", "beta_headers", "auto_cache"):
                body[k] = v

        return body, extra_headers

    def _translate_message(self, msg: Message) -> dict[str, Any] | None:
        role = "user" if msg.role in (Role.USER, Role.TOOL) else "assistant"
        content: list[dict[str, Any]] = []

        for part in msg.content:
            if part.kind == ContentKind.TEXT and part.text is not None:
                content.append({"type": "text", "text": part.text})
            elif part.kind == ContentKind.IMAGE and part.image:
                if part.image.url:
                    content.append(
                        {
                            "type": "image",
                            "source": {"type": "url", "url": part.image.url},
                        }
                    )
                elif part.image.data:
                    mt = part.image.media_type or "image/png"
                    b64 = base64.b64encode(part.image.data).decode()
                    content.append(
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": mt, "data": b64},
                        }
                    )
            elif part.kind == ContentKind.TOOL_CALL and part.tool_call:
                args = part.tool_call.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                content.append(
                    {
                        "type": "tool_use",
                        "id": part.tool_call.id,
                        "name": part.tool_call.name,
                        "input": args,
                    }
                )
            elif part.kind == ContentKind.TOOL_RESULT and part.tool_result:
                tr_content = part.tool_result.content
                if isinstance(tr_content, dict):
                    tr_content = json.dumps(tr_content)
                content.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": part.tool_result.tool_call_id,
                        "content": str(tr_content),
                        "is_error": part.tool_result.is_error,
                    }
                )
            elif part.kind == ContentKind.THINKING and part.thinking:
                content.append(
                    {
                        "type": "thinking",
                        "thinking": part.thinking.text,
                        **(
                            {"signature": part.thinking.signature}
                            if part.thinking.signature
                            else {}
                        ),
                    }
                )
            elif part.kind == ContentKind.REDACTED_THINKING and part.thinking:
                content.append(
                    {
                        "type": "redacted_thinking",
                        "data": part.thinking.text,
                    }
                )

        if not content:
            return None
        return {"role": role, "content": content}

    @staticmethod
    def _translate_tool(tool: ToolDefinition) -> dict[str, Any]:
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
        }

    def _parse_response(self, data: dict[str, Any]) -> Response:
        content_parts: list[ContentPart] = []

        for block in data.get("content", []):
            btype = block.get("type", "")
            if btype == "text":
                content_parts.append(ContentPart.text_part(block.get("text", "")))
            elif btype == "tool_use":
                content_parts.append(
                    ContentPart(
                        kind=ContentKind.TOOL_CALL,
                        tool_call=ToolCallData(
                            id=block.get("id", ""),
                            name=block.get("name", ""),
                            arguments=block.get("input", {}),
                        ),
                    )
                )
            elif btype == "thinking":
                content_parts.append(
                    ContentPart(
                        kind=ContentKind.THINKING,
                        thinking=ThinkingData(
                            text=block.get("thinking", ""),
                            signature=block.get("signature"),
                        ),
                    )
                )
            elif btype == "redacted_thinking":
                content_parts.append(
                    ContentPart(
                        kind=ContentKind.REDACTED_THINKING,
                        thinking=ThinkingData(
                            text=block.get("data", ""),
                            redacted=True,
                        ),
                    )
                )

        stop_reason = data.get("stop_reason", "end_turn")
        reason_map = {
            "end_turn": FinishReason.STOP,
            "stop_sequence": FinishReason.STOP,
            "max_tokens": FinishReason.LENGTH,
            "tool_use": FinishReason.TOOL_CALLS,
        }
        unified = reason_map.get(stop_reason, FinishReason.OTHER)

        usage_data = data.get("usage", {})
        return Response(
            id=data.get("id", ""),
            model=data.get("model", ""),
            provider="anthropic",
            message=Message(role=Role.ASSISTANT, content=content_parts),
            finish_reason=FinishReason(reason=unified, raw=stop_reason),
            usage=Usage(
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
                total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
                cache_read_tokens=usage_data.get("cache_read_input_tokens"),
                cache_write_tokens=usage_data.get("cache_creation_input_tokens"),
                raw=usage_data,
            ),
            raw=data,
        )

    async def complete(self, request: Request) -> Response:
        client = self._get_client()
        body, extra_headers = self._build_request_body(request)
        resp = await client.post("/v1/messages", json=body, headers=extra_headers)
        if resp.status_code != 200:
            self._raise_error(resp)
        return self._parse_response(resp.json())

    async def stream(self, request: Request) -> AsyncIterator[StreamEvent]:
        client = self._get_client()
        body, extra_headers = self._build_request_body(request)
        body["stream"] = True

        async with client.stream("POST", "/v1/messages", json=body, headers=extra_headers) as resp:
            if resp.status_code != 200:
                data = await resp.aread()
                self._raise_error_from_bytes(resp.status_code, data, resp.headers)

            accumulated_data: dict[str, Any] = {}
            current_block_type: str = ""
            current_block_id: str = ""

            async def _line_iter() -> AsyncIterator[str]:
                async for line in resp.aiter_lines():
                    yield line

            async for sse in parse_sse(_line_iter()):
                try:
                    ev = json.loads(sse.data)
                except json.JSONDecodeError:
                    continue

                ev_type = sse.event

                if ev_type == "message_start":
                    accumulated_data = ev.get("message", {})
                    yield StreamEvent(type=StreamEventType.STREAM_START)

                elif ev_type == "content_block_start":
                    block = ev.get("content_block", {})
                    current_block_type = block.get("type", "")
                    current_block_id = block.get("id", str(ev.get("index", "")))
                    if current_block_type == "text":
                        yield StreamEvent(type=StreamEventType.TEXT_START, text_id=current_block_id)
                    elif current_block_type == "tool_use":
                        yield StreamEvent(
                            type=StreamEventType.TOOL_CALL_START,
                            tool_call=ToolCall(
                                id=block.get("id", ""),
                                name=block.get("name", ""),
                            ),
                        )
                    elif current_block_type == "thinking":
                        yield StreamEvent(type=StreamEventType.REASONING_START)

                elif ev_type == "content_block_delta":
                    delta = ev.get("delta", {})
                    delta_type = delta.get("type", "")
                    if delta_type == "text_delta":
                        yield StreamEvent(
                            type=StreamEventType.TEXT_DELTA,
                            delta=delta.get("text", ""),
                            text_id=current_block_id,
                        )
                    elif delta_type == "input_json_delta":
                        yield StreamEvent(
                            type=StreamEventType.TOOL_CALL_DELTA,
                            tool_call=ToolCall(
                                id=current_block_id,
                                raw_arguments=delta.get("partial_json", ""),
                            ),
                        )
                    elif delta_type == "thinking_delta":
                        yield StreamEvent(
                            type=StreamEventType.REASONING_DELTA,
                            reasoning_delta=delta.get("thinking", ""),
                        )

                elif ev_type == "content_block_stop":
                    if current_block_type == "text":
                        yield StreamEvent(type=StreamEventType.TEXT_END, text_id=current_block_id)
                    elif current_block_type == "tool_use":
                        yield StreamEvent(
                            type=StreamEventType.TOOL_CALL_END,
                            tool_call=ToolCall(id=current_block_id),
                        )
                    elif current_block_type == "thinking":
                        yield StreamEvent(type=StreamEventType.REASONING_END)

                elif ev_type == "message_delta":
                    delta = ev.get("delta", {})
                    usage_data = ev.get("usage", {})
                    stop_reason = delta.get("stop_reason", "end_turn")
                    reason_map = {
                        "end_turn": FinishReason.STOP,
                        "stop_sequence": FinishReason.STOP,
                        "max_tokens": FinishReason.LENGTH,
                        "tool_use": FinishReason.TOOL_CALLS,
                    }
                    yield StreamEvent(
                        type=StreamEventType.FINISH,
                        finish_reason=FinishReason(
                            reason=reason_map.get(stop_reason, FinishReason.OTHER),
                            raw=stop_reason,
                        ),
                        usage=Usage(
                            output_tokens=usage_data.get("output_tokens", 0),
                            input_tokens=accumulated_data.get("usage", {}).get("input_tokens", 0),
                            total_tokens=(
                                accumulated_data.get("usage", {}).get("input_tokens", 0)
                                + usage_data.get("output_tokens", 0)
                            ),
                            cache_read_tokens=accumulated_data.get("usage", {}).get(
                                "cache_read_input_tokens"
                            ),
                            cache_write_tokens=accumulated_data.get("usage", {}).get(
                                "cache_creation_input_tokens"
                            ),
                        ),
                    )

    def _raise_error(self, resp: httpx.Response) -> None:
        try:
            body = resp.json()
            message = body.get("error", {}).get("message", resp.text)
            code = body.get("error", {}).get("type")
        except Exception:
            message = resp.text
            code = None
            body = None

        retry_after = resp.headers.get("retry-after")
        ra_float = float(retry_after) if retry_after else None

        raise error_from_status_code(
            status_code=resp.status_code,
            message=message,
            provider="anthropic",
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
            code = body.get("error", {}).get("type")
        except Exception:
            message = data.decode(errors="replace")
            code = None
            body = None

        retry_after = headers.get("retry-after")
        ra_float = float(retry_after) if retry_after else None

        raise error_from_status_code(
            status_code=status_code,
            message=message,
            provider="anthropic",
            error_code=code,
            raw=body,
            retry_after=ra_float,
        )
