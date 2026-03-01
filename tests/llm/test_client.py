"""Tests for attractor.llm.client."""

from __future__ import annotations

import pytest

from attractor.llm.client import Client
from attractor.llm.errors import ConfigurationError
from attractor.llm.models import (
    ContentPart,
    FinishReason,
    Message,
    Request,
    Response,
    Role,
    StreamEventType,
    Usage,
)
from tests.conftest import FakeAdapter


def _make_adapter(name: str, reply: str = "hello") -> FakeAdapter:
    return FakeAdapter(
        canned_response=Response(
            model=f"{name}-model",
            provider=name,
            message=Message(
                role=Role.ASSISTANT,
                content=[ContentPart.text_part(reply)],
            ),
            finish_reason=FinishReason(reason=FinishReason.STOP),
            usage=Usage(input_tokens=5, output_tokens=3, total_tokens=8),
        )
    )


# ---------------------------------------------------------------------------
# Provider routing
# ---------------------------------------------------------------------------


class TestProviderRouting:
    async def test_routes_to_correct_provider(self):
        openai = _make_adapter("openai", "openai reply")
        anthropic = _make_adapter("anthropic", "anthropic reply")
        client = Client(
            providers={"openai": openai, "anthropic": anthropic},
            default_provider="openai",
        )
        request = Request(model="gpt-5.2", provider="anthropic")
        resp = await client.complete(request)
        assert resp.provider == "anthropic"
        assert resp.text == "anthropic reply"
        assert len(anthropic._requests) == 1
        assert len(openai._requests) == 0

    async def test_uses_default_provider_when_none(self):
        openai = _make_adapter("openai", "default reply")
        client = Client(
            providers={"openai": openai},
            default_provider="openai",
        )
        request = Request(model="gpt-5.2", provider=None)
        resp = await client.complete(request)
        assert resp.text == "default reply"
        assert len(openai._requests) == 1

    async def test_auto_default_provider_is_first_key(self):
        adapter = _make_adapter("only")
        client = Client(providers={"only": adapter})
        request = Request(model="m")
        resp = await client.complete(request)
        assert resp.text == "hello"


# ---------------------------------------------------------------------------
# ConfigurationError
# ---------------------------------------------------------------------------


class TestConfigurationError:
    async def test_unregistered_provider_raises(self):
        client = Client(providers={"openai": _make_adapter("openai")})
        request = Request(model="m", provider="anthropic")
        with pytest.raises(ConfigurationError, match="not registered"):
            await client.complete(request)

    async def test_no_provider_no_default_raises(self):
        client = Client(providers={})
        request = Request(model="m")
        with pytest.raises(ConfigurationError, match="No provider"):
            await client.complete(request)


# ---------------------------------------------------------------------------
# register_provider
# ---------------------------------------------------------------------------


class TestRegisterProvider:
    async def test_register_and_use(self):
        client = Client()
        adapter = _make_adapter("custom", "custom reply")
        client.register_provider("custom", adapter)
        request = Request(model="m")
        resp = await client.complete(request)
        assert resp.text == "custom reply"


# ---------------------------------------------------------------------------
# Middleware chain
# ---------------------------------------------------------------------------


class TestMiddleware:
    async def test_single_middleware(self):
        call_order: list[str] = []

        async def mw(request: Request, next_fn) -> Response:
            call_order.append("mw_before")
            resp = await next_fn(request)
            call_order.append("mw_after")
            return resp

        adapter = _make_adapter("test")
        client = Client(
            providers={"test": adapter},
            middleware=[mw],
        )
        request = Request(model="m")
        await client.complete(request)
        assert call_order == ["mw_before", "mw_after"]

    async def test_middleware_chain_executes_in_order(self):
        call_order: list[str] = []

        async def mw1(request: Request, next_fn) -> Response:
            call_order.append("mw1_before")
            resp = await next_fn(request)
            call_order.append("mw1_after")
            return resp

        async def mw2(request: Request, next_fn) -> Response:
            call_order.append("mw2_before")
            resp = await next_fn(request)
            call_order.append("mw2_after")
            return resp

        adapter = _make_adapter("test")
        client = Client(
            providers={"test": adapter},
            middleware=[mw1, mw2],
        )
        request = Request(model="m")
        await client.complete(request)
        assert call_order == ["mw1_before", "mw2_before", "mw2_after", "mw1_after"]

    async def test_middleware_can_modify_request(self):
        async def add_header_mw(request: Request, next_fn) -> Response:
            request.metadata = {"injected": "true"}
            return await next_fn(request)

        adapter = _make_adapter("test")
        client = Client(
            providers={"test": adapter},
            middleware=[add_header_mw],
        )
        request = Request(model="m")
        await client.complete(request)
        assert adapter._requests[0].metadata == {"injected": "true"}

    async def test_middleware_can_modify_response(self):
        async def tag_mw(request: Request, next_fn) -> Response:
            resp = await next_fn(request)
            resp.raw = {"tagged": True}
            return resp

        adapter = _make_adapter("test")
        client = Client(
            providers={"test": adapter},
            middleware=[tag_mw],
        )
        request = Request(model="m")
        resp = await client.complete(request)
        assert resp.raw == {"tagged": True}


# ---------------------------------------------------------------------------
# Stream
# ---------------------------------------------------------------------------


class TestStream:
    async def test_stream_returns_events(self):
        adapter = _make_adapter("test")
        client = Client(providers={"test": adapter})
        request = Request(model="m")
        event_iter = await client.stream(request)
        events = [e async for e in event_iter]
        assert len(events) > 0
        assert any(e.type == StreamEventType.FINISH for e in events)


# ---------------------------------------------------------------------------
# Close
# ---------------------------------------------------------------------------


class TestClose:
    async def test_close_calls_adapter_close(self):
        adapter = _make_adapter("test")
        closed = False
        original_close = adapter.close

        async def track_close():
            nonlocal closed
            closed = True
            await original_close()

        adapter.close = track_close
        client = Client(providers={"test": adapter})
        await client.close()
        assert closed is True
