"""Integration smoke tests for the Coding Agent Loop - requires real API keys."""

import os

import pytest

from attractor.agent.config import SessionConfig
from attractor.agent.execution.local import LocalExecutionEnvironment
from attractor.agent.profiles.anthropic import AnthropicProfile
from attractor.agent.profiles.openai import OpenAIProfile
from attractor.agent.session import Session
from attractor.llm.client import Client

pytestmark = [pytest.mark.integration]


def _make_session(provider: str, tmp_dir: str) -> Session | None:
    client = Client.from_env()
    env = LocalExecutionEnvironment(working_dir=tmp_dir)
    config = SessionConfig(max_tool_rounds_per_input=5, default_command_timeout_ms=10000)

    if provider == "openai" and os.environ.get("OPENAI_API_KEY"):
        return Session(client=client, profile=OpenAIProfile(), environment=env, config=config)
    elif provider == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
        return Session(client=client, profile=AnthropicProfile(), environment=env, config=config)
    return None


PROVIDERS = []
if os.environ.get("OPENAI_API_KEY"):
    PROVIDERS.append("openai")
if os.environ.get("ANTHROPIC_API_KEY"):
    PROVIDERS.append("anthropic")

skip_no_providers = pytest.mark.skipif(not PROVIDERS, reason="No API keys set")


@skip_no_providers
@pytest.mark.parametrize("provider", PROVIDERS)
async def test_simple_file_creation(provider: str, tmp_path):
    session = _make_session(provider, str(tmp_path))
    if not session:
        pytest.skip(f"No API key for {provider}")

    result = await session.process_input(
        "Create a file called hello.py that prints 'Hello, World!'"
    )
    assert result.text or result.tool_calls_made > 0
    await session.close()


@skip_no_providers
@pytest.mark.parametrize("provider", PROVIDERS)
async def test_shell_execution(provider: str, tmp_path):
    session = _make_session(provider, str(tmp_path))
    if not session:
        pytest.skip(f"No API key for {provider}")

    result = await session.process_input("Run the command: echo 'test output'")
    assert result.text or result.tool_calls_made > 0
    await session.close()
