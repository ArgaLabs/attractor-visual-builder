"""Integration smoke tests for LLM SDK - requires real API keys."""

import os

import pytest

from attractor.llm.generate import generate, stream_generate
from attractor.llm.models import StreamEventType
from attractor.llm.tools import Tool

pytestmark = [pytest.mark.integration]

PROVIDERS = []
if os.environ.get("OPENAI_API_KEY"):
    PROVIDERS.append("openai")
if os.environ.get("ANTHROPIC_API_KEY"):
    PROVIDERS.append("anthropic")
if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
    PROVIDERS.append("gemini")

MODEL_MAP = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-5-20250514",
    "gemini": "gemini-2.0-flash",
}

skip_no_providers = pytest.mark.skipif(not PROVIDERS, reason="No API keys set")


@skip_no_providers
@pytest.mark.parametrize("provider", PROVIDERS)
async def test_simple_text_generation(provider: str):
    result = await generate(
        model=MODEL_MAP[provider],
        prompt="Say 'hello world' and nothing else.",
        provider=provider,
        max_tool_rounds=0,
    )
    assert result.text
    assert result.usage.total_tokens > 0
    assert result.finish_reason.reason == "stop"


@skip_no_providers
@pytest.mark.parametrize("provider", PROVIDERS)
async def test_streaming(provider: str):
    stream = await stream_generate(
        model=MODEL_MAP[provider],
        prompt="Count from 1 to 5.",
        provider=provider,
    )
    deltas = []
    async for event in stream:
        if event.type == StreamEventType.TEXT_DELTA:
            deltas.append(event.delta)
    full_text = "".join(d for d in deltas if d)
    assert len(full_text) > 0


@skip_no_providers
@pytest.mark.parametrize("provider", PROVIDERS)
async def test_tool_calling(provider: str):
    weather_tool = Tool(
        name="get_weather",
        description="Get weather for a city",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string"},
            },
            "required": ["city"],
        },
        execute=lambda city: f"72°F and sunny in {city}",
    )
    result = await generate(
        model=MODEL_MAP[provider],
        prompt="What's the weather in Tokyo and London?",
        provider=provider,
        tools=[weather_tool],
        max_tool_rounds=3,
    )
    assert result.text
    assert result.total_usage.total_tokens > 0


@skip_no_providers
@pytest.mark.parametrize("provider", PROVIDERS)
async def test_error_nonexistent_model(provider: str):
    with pytest.raises(Exception):
        await generate(
            model="nonexistent-model-xyz",
            prompt="Hello",
            provider=provider,
            max_retries=0,
        )
