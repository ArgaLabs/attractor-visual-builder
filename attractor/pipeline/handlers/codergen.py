"""Codergen handler: prompt expansion, LLM backend call, log writing."""

from __future__ import annotations

import abc
import json
import os
from typing import Any

from attractor.pipeline.handlers.base import Handler, HandlerInput
from attractor.pipeline.outcome import Outcome, StageStatus


class CodergenBackend(abc.ABC):
    @abc.abstractmethod
    async def run(self, node_id: str, prompt: str, context: dict[str, Any]) -> Outcome | str: ...


class CodergenHandler(Handler):
    def __init__(self, backend: CodergenBackend | None = None):
        self._backend = backend

    async def execute(self, input: HandlerInput) -> Outcome:
        prompt = input.node.prompt
        goal = input.context.get("goal", input.graph.goal)

        prompt = prompt.replace("$goal", str(goal))

        for key in input.context.keys():
            placeholder = f"${{context.{key}}}"
            if placeholder in prompt:
                prompt = prompt.replace(placeholder, str(input.context.get(key, "")))

        if input.stage_dir:
            os.makedirs(input.stage_dir, exist_ok=True)
            with open(os.path.join(input.stage_dir, "prompt.md"), "w") as f:
                f.write(prompt)

        if self._backend is None:
            response_text = f"[Simulated response for node {input.node.id}]"
            outcome = Outcome(
                status=StageStatus.SUCCESS,
                message=response_text,
                context_updates={"last_response": response_text},
            )
        else:
            result = await self._backend.run(input.node.id, prompt, input.context.snapshot())
            if isinstance(result, Outcome):
                outcome = result
            else:
                outcome = Outcome(
                    status=StageStatus.SUCCESS,
                    message=str(result),
                    context_updates={"last_response": str(result)},
                )

        if input.stage_dir:
            with open(os.path.join(input.stage_dir, "response.md"), "w") as f:
                f.write(outcome.message)
            with open(os.path.join(input.stage_dir, "status.json"), "w") as f:
                json.dump({"status": outcome.status.value, "node_id": input.node.id}, f)

        return outcome
