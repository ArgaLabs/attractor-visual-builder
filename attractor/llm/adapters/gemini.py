"""Gemini adapter using the native Gemini API."""

from __future__ import annotations

import base64
import json
import os
import uuid
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
    ToolDefinition,
    Usage,
)
from attractor.llm.streaming import parse_sse


class GeminiAdapter(ProviderAdapter):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://generativelanguage.googleapis.com",
        timeout: float = 120.0,
    ):
        self._api_key = (
            api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
        )
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._call_id_to_name: dict[str, str] = {}

    @property
    def name(self) -> str:
        return "gemini"

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout, connect=10.0),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _build_request_body(self, request: Request) -> dict[str, Any]:
        body: dict[str, Any] = {}

        system_parts: list[str] = []
        contents: list[dict[str, Any]] = []

        for msg in request.messages:
            if msg.role in (Role.SYSTEM, Role.DEVELOPER):
                system_parts.append(msg.text)
                continue

            role = "model" if msg.role == Role.ASSISTANT else "user"
            parts: list[dict[str, Any]] = []

            for part in msg.content:
                if part.kind == ContentKind.TEXT and part.text is not None:
                    parts.append({"text": part.text})
                elif part.kind == ContentKind.IMAGE and part.image:
                    if part.image.url:
                        parts.append(
                            {
                                "fileData": {
                                    "mimeType": part.image.media_type or "image/png",
                                    "fileUri": part.image.url,
                                },
                            }
                        )
                    elif part.image.data:
                        mt = part.image.media_type or "image/png"
                        b64 = base64.b64encode(part.image.data).decode()
                        parts.append({"inlineData": {"mimeType": mt, "data": b64}})
                elif part.kind == ContentKind.TOOL_CALL and part.tool_call:
                    args = part.tool_call.arguments
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except (json.JSONDecodeError, TypeError):
                            args = {}
                    parts.append(
                        {
                            "functionCall": {"name": part.tool_call.name, "args": args},
                        }
                    )
                elif part.kind == ContentKind.TOOL_RESULT and part.tool_result:
                    call_id = part.tool_result.tool_call_id
                    fn_name = self._call_id_to_name.get(call_id, call_id)
                    resp_content = part.tool_result.content
                    if isinstance(resp_content, str):
                        resp_content = {"result": resp_content}
                    parts.append(
                        {
                            "functionResponse": {"name": fn_name, "response": resp_content},
                        }
                    )

            if parts:
                if contents and contents[-1]["role"] == role:
                    contents[-1]["parts"].extend(parts)
                else:
                    contents.append({"role": role, "parts": parts})

        if system_parts:
            body["systemInstruction"] = {
                "parts": [{"text": "\n\n".join(system_parts)}],
            }

        body["contents"] = contents

        gen_config: dict[str, Any] = {}
        if request.temperature is not None:
            gen_config["temperature"] = request.temperature
        if request.top_p is not None:
            gen_config["topP"] = request.top_p
        if request.max_tokens is not None:
            gen_config["maxOutputTokens"] = request.max_tokens
        if request.stop_sequences:
            gen_config["stopSequences"] = request.stop_sequences

        if request.response_format and request.response_format.type in ("json", "json_schema"):
            gen_config["responseMimeType"] = "application/json"
            if request.response_format.json_schema:
                gen_config["responseSchema"] = request.response_format.json_schema

        if request.reasoning_effort:
            effort_map = {"low": 1024, "medium": 8192, "high": 24576}
            budget = effort_map.get(request.reasoning_effort, 8192)
            gen_config["thinkingConfig"] = {"thinkingBudget": budget}

        if gen_config:
            body["generationConfig"] = gen_config

        if request.tools:
            body["tools"] = [
                {"functionDeclarations": [self._translate_tool(t) for t in request.tools]}
            ]

        if request.tool_choice:
            tc = request.tool_choice
            if tc.mode == "auto":
                body["toolConfig"] = {"functionCallingConfig": {"mode": "AUTO"}}
            elif tc.mode == "none":
                body["toolConfig"] = {"functionCallingConfig": {"mode": "NONE"}}
            elif tc.mode == "required":
                body["toolConfig"] = {"functionCallingConfig": {"mode": "ANY"}}
            elif tc.mode == "named" and tc.tool_name:
                body["toolConfig"] = {
                    "functionCallingConfig": {
                        "mode": "ANY",
                        "allowedFunctionNames": [tc.tool_name],
                    }
                }

        opts = (request.provider_options or {}).get("gemini", {})
        for k, v in opts.items():
            body[k] = v

        return body

    @staticmethod
    def _translate_tool(tool: ToolDefinition) -> dict[str, Any]:
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }

    def _parse_response(self, data: dict[str, Any], model: str = "") -> Response:
        content_parts: list[ContentPart] = []
        has_tool_calls = False

        candidates = data.get("candidates", [])
        finish_reason_raw = ""
        if candidates:
            candidate = candidates[0]
            finish_reason_raw = candidate.get("finishReason", "")
            for part in candidate.get("content", {}).get("parts", []):
                if "text" in part:
                    content_parts.append(ContentPart.text_part(part["text"]))
                elif "functionCall" in part:
                    fc = part["functionCall"]
                    call_id = f"call_{uuid.uuid4().hex[:12]}"
                    fn_name = fc.get("name", "")
                    self._call_id_to_name[call_id] = fn_name
                    content_parts.append(
                        ContentPart(
                            kind=ContentKind.TOOL_CALL,
                            tool_call=ToolCallData(
                                id=call_id,
                                name=fn_name,
                                arguments=fc.get("args", {}),
                            ),
                        )
                    )
                    has_tool_calls = True
                elif "thought" in part:
                    content_parts.append(ContentPart.thinking_part(part.get("thought", "")))

        reason_map = {
            "STOP": FinishReason.STOP,
            "MAX_TOKENS": FinishReason.LENGTH,
            "SAFETY": FinishReason.CONTENT_FILTER,
            "RECITATION": FinishReason.CONTENT_FILTER,
        }
        if has_tool_calls:
            unified = FinishReason.TOOL_CALLS
        else:
            unified = reason_map.get(finish_reason_raw, FinishReason.STOP)

        usage_meta = data.get("usageMetadata", {})
        return Response(
            id=data.get("responseId", ""),
            model=model or data.get("modelVersion", ""),
            provider="gemini",
            message=Message(role=Role.ASSISTANT, content=content_parts),
            finish_reason=FinishReason(reason=unified, raw=finish_reason_raw),
            usage=Usage(
                input_tokens=usage_meta.get("promptTokenCount", 0),
                output_tokens=usage_meta.get("candidatesTokenCount", 0),
                total_tokens=usage_meta.get("totalTokenCount", 0),
                reasoning_tokens=usage_meta.get("thoughtsTokenCount"),
                cache_read_tokens=usage_meta.get("cachedContentTokenCount"),
                raw=usage_meta,
            ),
            raw=data,
        )

    async def complete(self, request: Request) -> Response:
        client = self._get_client()
        body = self._build_request_body(request)
        url = f"/v1beta/models/{request.model}:generateContent?key={self._api_key}"
        resp = await client.post(url, json=body)
        if resp.status_code != 200:
            self._raise_error(resp)
        return self._parse_response(resp.json(), model=request.model)

    async def stream(self, request: Request) -> AsyncIterator[StreamEvent]:
        client = self._get_client()
        body = self._build_request_body(request)
        url = f"/v1beta/models/{request.model}:streamGenerateContent?key={self._api_key}&alt=sse"

        text_started = False

        async with client.stream("POST", url, json=body) as resp:
            if resp.status_code != 200:
                data = await resp.aread()
                self._raise_error_from_bytes(resp.status_code, data, resp.headers)

            async def _line_iter() -> AsyncIterator[str]:
                async for line in resp.aiter_lines():
                    yield line

            last_chunk: dict[str, Any] = {}

            async for sse in parse_sse(_line_iter()):
                try:
                    chunk = json.loads(sse.data)
                except json.JSONDecodeError:
                    continue

                last_chunk = chunk
                candidates = chunk.get("candidates", [])
                if not candidates:
                    continue

                candidate = candidates[0]
                for part in candidate.get("content", {}).get("parts", []):
                    if "text" in part:
                        if not text_started:
                            yield StreamEvent(type=StreamEventType.TEXT_START, text_id="0")
                            text_started = True
                        yield StreamEvent(
                            type=StreamEventType.TEXT_DELTA,
                            delta=part["text"],
                            text_id="0",
                        )
                    elif "functionCall" in part:
                        fc = part["functionCall"]
                        call_id = f"call_{uuid.uuid4().hex[:12]}"
                        fn_name = fc.get("name", "")
                        self._call_id_to_name[call_id] = fn_name
                        tc = ToolCall(id=call_id, name=fn_name, arguments=fc.get("args", {}))
                        yield StreamEvent(type=StreamEventType.TOOL_CALL_START, tool_call=tc)
                        yield StreamEvent(type=StreamEventType.TOOL_CALL_END, tool_call=tc)

                if candidate.get("finishReason"):
                    if text_started:
                        yield StreamEvent(type=StreamEventType.TEXT_END, text_id="0")
                        text_started = False

            if last_chunk:
                parsed = self._parse_response(last_chunk, model=request.model)
                yield StreamEvent(
                    type=StreamEventType.FINISH,
                    finish_reason=parsed.finish_reason,
                    usage=parsed.usage,
                    response=parsed,
                )

    def _raise_error(self, resp: httpx.Response) -> None:
        try:
            body = resp.json()
            err = body.get("error", {})
            message = err.get("message", resp.text)
            code = err.get("status") or err.get("code")
        except Exception:
            message = resp.text
            code = None
            body = None

        raise error_from_status_code(
            status_code=resp.status_code,
            message=message,
            provider="gemini",
            error_code=str(code) if code else None,
            raw=body,
        )

    def _raise_error_from_bytes(
        self, status_code: int, data: bytes, headers: httpx.Headers
    ) -> None:
        try:
            body = json.loads(data)
            message = body.get("error", {}).get("message", data.decode())
            code = body.get("error", {}).get("status")
        except Exception:
            message = data.decode(errors="replace")
            code = None
            body = None

        raise error_from_status_code(
            status_code=status_code,
            message=message,
            provider="gemini",
            error_code=str(code) if code else None,
            raw=body,
        )
