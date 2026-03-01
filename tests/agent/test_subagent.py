"""Tests for attractor.agent.subagent."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from attractor.agent.execution.local import LocalExecutionEnvironment
from attractor.agent.profiles.anthropic import AnthropicProfile
from attractor.agent.session import Session
from attractor.agent.subagent import SubagentManager
from attractor.llm.adapters.base import ProviderAdapter
from attractor.llm.client import Client
from attractor.llm.models import (
    FinishReason,
    Message,
    Request,
    Response,
    StreamEvent,
    Usage,
)


class FakeAdapter(ProviderAdapter):
    def __init__(self, text: str = "subagent response"):
        self._text = text

    @property
    def name(self) -> str:
        return "fake"

    async def complete(self, request: Request) -> Response:
        return Response(
            message=Message.assistant(self._text),
            finish_reason=FinishReason(reason="stop"),
            usage=Usage(input_tokens=5, output_tokens=5, total_tokens=10),
        )

    async def stream(self, request: Request) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError

        yield  # type: ignore[misc]


def _make_parent_session(tmp_path, text: str = "parent response") -> Session:
    adapter = FakeAdapter(text)
    client = Client(providers={"anthropic": adapter}, default_provider="anthropic")
    env = LocalExecutionEnvironment(working_dir=str(tmp_path))
    profile = AnthropicProfile()
    return Session(client=client, profile=profile, environment=env)


class TestSubagentManagerSpawn:
    async def test_spawn_creates_child_session(self, tmp_path):
        parent = _make_parent_session(tmp_path)
        manager = SubagentManager(max_depth=2)

        handle = await manager.spawn(parent, "do something", depth=0)

        assert handle.id.startswith("sub_")
        result = await handle.wait()
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_spawn_returns_result(self, tmp_path):
        parent = _make_parent_session(tmp_path, text="child says hi")
        manager = SubagentManager(max_depth=2)

        handle = await manager.spawn(parent, "greet", depth=0)
        result = await handle.wait()
        assert "child says hi" in result

    async def test_spawn_agent_can_be_retrieved(self, tmp_path):
        parent = _make_parent_session(tmp_path)
        manager = SubagentManager(max_depth=2)

        handle = await manager.spawn(parent, "task", depth=0)
        retrieved = manager.get(handle.id)
        assert retrieved is handle

    async def test_get_unknown_returns_none(self, tmp_path):
        manager = SubagentManager(max_depth=2)
        assert manager.get("nonexistent") is None


class TestMaxDepthEnforcement:
    async def test_max_depth_zero_raises(self, tmp_path):
        parent = _make_parent_session(tmp_path)
        manager = SubagentManager(max_depth=1)

        with pytest.raises(ValueError, match="Max subagent depth"):
            await manager.spawn(parent, "too deep", depth=1)

    async def test_max_depth_exceeded_raises(self, tmp_path):
        parent = _make_parent_session(tmp_path)
        manager = SubagentManager(max_depth=2)

        with pytest.raises(ValueError, match="Max subagent depth"):
            await manager.spawn(parent, "too deep", depth=2)

    async def test_within_depth_succeeds(self, tmp_path):
        parent = _make_parent_session(tmp_path)
        manager = SubagentManager(max_depth=3)

        handle = await manager.spawn(parent, "ok", depth=2)
        assert handle.id.startswith("sub_")


class TestCloseAll:
    async def test_close_all_clears_agents(self, tmp_path):
        parent = _make_parent_session(tmp_path)
        manager = SubagentManager(max_depth=5)

        h1 = await manager.spawn(parent, "a", depth=0)
        h2 = await manager.spawn(parent, "b", depth=0)
        assert manager.get(h1.id) is not None
        assert manager.get(h2.id) is not None

        manager.close_all()

        assert manager.get(h1.id) is None
        assert manager.get(h2.id) is None
