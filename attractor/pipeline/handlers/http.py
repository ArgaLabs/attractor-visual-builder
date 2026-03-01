"""HTTP handler: make outbound HTTP requests to external skills or webhook endpoints."""

from __future__ import annotations

import json
from typing import Any

import httpx

from attractor.pipeline.handlers.base import Handler, HandlerInput
from attractor.pipeline.outcome import Outcome, StageStatus

_SUPPORTED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _interpolate(value: str, context: dict[str, Any]) -> str:
    """Replace $key and ${key} placeholders with values from context."""
    for k, v in context.items():
        value = value.replace(f"${{{k}}}", str(v))
        value = value.replace(f"${k}", str(v))
    return value


class HttpHandler(Handler):
    """Execute an outbound HTTP request and store the response in pipeline context.

    Node attributes (all support $variable interpolation from pipeline context):
        url         (required) Full URL to call.
        method      HTTP method — GET, POST, PUT, PATCH, DELETE. Default: GET.
        body        JSON-serialisable string to send as request body (for POST/PUT/PATCH).
        headers     JSON object string of additional request headers.
        timeout     Request timeout in seconds. Default: 30.

    On success the following keys are written to context:
        http.status_code    Integer HTTP status code.
        http.body           Response body text.
        http.json           Parsed JSON body (if response is JSON), else None.
        outcome             "success" if 2xx, "failure" otherwise.
    """

    async def execute(self, input: HandlerInput) -> Outcome:
        attrs = input.node.attrs
        ctx_snapshot = input.context.snapshot()

        url = attrs.get("url", "")
        if not url:
            return Outcome(
                status=StageStatus.FAIL,
                message="HTTP node requires a 'url' attribute",
            )

        url = _interpolate(str(url), ctx_snapshot)
        method = str(attrs.get("method", "GET")).upper()
        if method not in _SUPPORTED_METHODS:
            return Outcome(
                status=StageStatus.FAIL,
                message=f"Unsupported HTTP method '{method}'. Use one of: {', '.join(_SUPPORTED_METHODS)}",
            )

        timeout = float(attrs.get("timeout", input.node.timeout or 30))

        # Headers
        headers: dict[str, str] = {"Content-Type": "application/json"}
        raw_headers = attrs.get("headers", "")
        if raw_headers:
            try:
                extra = json.loads(_interpolate(str(raw_headers), ctx_snapshot))
                if isinstance(extra, dict):
                    headers.update({str(k): str(v) for k, v in extra.items()})
            except json.JSONDecodeError as exc:
                return Outcome(
                    status=StageStatus.FAIL,
                    message=f"Invalid JSON in 'headers' attribute: {exc}",
                )

        # Body
        content: bytes | None = None
        raw_body = attrs.get("body", "")
        if raw_body:
            body_str = _interpolate(str(raw_body), ctx_snapshot)
            content = body_str.encode()

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    content=content,
                    headers=headers,
                )
        except httpx.TimeoutException:
            return Outcome(
                status=StageStatus.FAIL,
                message=f"HTTP request timed out after {timeout}s",
            )
        except httpx.RequestError as exc:
            return Outcome(
                status=StageStatus.FAIL,
                message=f"HTTP request error: {exc}",
            )

        body_text = response.text
        parsed_json: Any = None
        try:
            parsed_json = response.json()
        except Exception:
            parsed_json = None

        is_success = response.is_success  # 2xx

        context_updates: dict[str, Any] = {
            "http.status_code": response.status_code,
            "http.body": body_text,
            "http.json": parsed_json,
            "outcome": "success" if is_success else "failure",
        }

        if is_success:
            return Outcome(
                status=StageStatus.SUCCESS,
                message=f"HTTP {method} {url} → {response.status_code}",
                context_updates=context_updates,
            )
        else:
            return Outcome(
                status=StageStatus.FAIL,
                message=f"HTTP {method} {url} returned {response.status_code}: {body_text[:200]}",
                context_updates=context_updates,
            )
