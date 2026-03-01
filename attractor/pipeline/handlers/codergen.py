"""Codergen handler: prompt expansion, LLM backend call, log writing."""

from __future__ import annotations

import abc
import json
import os
from typing import TYPE_CHECKING, Any

from attractor.pipeline.handlers.base import Handler, HandlerInput
from attractor.pipeline.outcome import Outcome, StageStatus

if TYPE_CHECKING:
    from attractor.llm.tools import Tool
    from attractor.mcp.bridge import MCPSession


class CodergenBackend(abc.ABC):
    @abc.abstractmethod
    async def run(
        self,
        node_id: str,
        prompt: str,
        context: dict[str, Any],
        tools: "list[Tool] | None" = None,
    ) -> "Outcome | str": ...


class CodergenHandler(Handler):
    def __init__(
        self,
        backend: "CodergenBackend | None" = None,
        mcp_session: "MCPSession | None" = None,
    ):
        self._backend = backend
        self._mcp_session = mcp_session

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

        # Collect MCP tools for this node if a session is attached
        tools = None
        if self._mcp_session is not None:
            try:
                tools = await self._mcp_session.all_tools()
            except Exception as exc:
                return Outcome(
                    status=StageStatus.FAIL,
                    message=f"MCP tool discovery failed: {exc}",
                )

        if self._backend is None:
            response_text = f"[Simulated response for node {input.node.id}]"
            outcome = Outcome(
                status=StageStatus.SUCCESS,
                message=response_text,
                context_updates={"last_response": response_text},
            )
        else:
            result = await self._backend.run(input.node.id, prompt, input.context.snapshot(), tools=tools)
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
