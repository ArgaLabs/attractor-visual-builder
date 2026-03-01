"""Manager loop: supervisor pattern with observe/guard/steer cycles."""

from __future__ import annotations

from typing import Any

from attractor.pipeline.handlers.base import Handler, HandlerInput
from attractor.pipeline.outcome import Outcome, StageStatus


class ManagerLoopHandler(Handler):
    def __init__(self, observe_fn: Any = None, guard_fn: Any = None, steer_fn: Any = None):
        self._observe = observe_fn
        self._guard = guard_fn
        self._steer = steer_fn

    async def execute(self, input: HandlerInput) -> Outcome:
        max_cycles = int(input.node.attrs.get("max_cycles", 3))
        cycle_count = 0

        while cycle_count < max_cycles:
            cycle_count += 1

            observation = None
            if self._observe:
                observation = await self._observe(input)

            should_continue = True
            if self._guard:
                should_continue = await self._guard(input, observation)

            if not should_continue:
                return Outcome(
                    status=StageStatus.SUCCESS,
                    message=f"Manager loop completed after {cycle_count} cycles (guard stopped)",
                    context_updates={"manager.cycles": cycle_count},
                )

            if self._steer:
                await self._steer(input, observation)

        return Outcome(
            status=StageStatus.SUCCESS,
            message=f"Manager loop completed after {cycle_count} cycles (max reached)",
            context_updates={"manager.cycles": cycle_count},
        )
