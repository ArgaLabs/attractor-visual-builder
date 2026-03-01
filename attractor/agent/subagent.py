"""Subagent management for the coding agent."""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from attractor.agent.session import Session


class SubagentHandle:
    def __init__(self, agent_id: str, session: Session):
        self.id = agent_id
        self._session = session
        self._result: str | None = None
        self._done_event = asyncio.Event()

    async def send_input(self, text: str) -> None:
        result = await self._session.process_input(text)
        self._result = result.text if result else ""

    async def wait(self) -> str:
        if self._result is not None:
            return self._result
        await self._done_event.wait()
        return self._result or ""

    def close(self) -> None:
        self._done_event.set()


class SubagentManager:
    def __init__(self, max_depth: int = 1):
        self._max_depth = max_depth
        self._agents: dict[str, SubagentHandle] = {}

    async def spawn(
        self,
        parent_session: Any,
        prompt: str,
        depth: int = 0,
    ) -> SubagentHandle:
        if depth >= self._max_depth:
            raise ValueError(f"Max subagent depth ({self._max_depth}) reached")

        from attractor.agent.session import Session

        agent_id = f"sub_{uuid.uuid4().hex[:8]}"

        child_session = Session(
            client=parent_session._client,
            profile=parent_session._profile,
            environment=parent_session._environment,
            config=parent_session._config,
        )

        handle = SubagentHandle(agent_id, child_session)
        self._agents[agent_id] = handle

        result = await child_session.process_input(prompt)
        handle._result = result.text if result else ""
        handle._done_event.set()

        return handle

    def get(self, agent_id: str) -> SubagentHandle | None:
        return self._agents.get(agent_id)

    def close_all(self) -> None:
        for handle in self._agents.values():
            handle.close()
        self._agents.clear()
