"""Wait-for-human handler: derives choices from edges, presents via Interviewer."""

from __future__ import annotations

import re
from typing import Any

from attractor.pipeline.handlers.base import Handler, HandlerInput
from attractor.pipeline.outcome import Outcome, StageStatus


class WaitForHumanHandler(Handler):
    def __init__(
        self,
        interviewer: Any = None,
        timeout: float | None = None,
        default_choice: str | None = None,
    ):
        self._interviewer = interviewer
        self._timeout = timeout
        self._default_choice = default_choice

    async def execute(self, input: HandlerInput) -> Outcome:
        edges = input.graph.outgoing_edges(input.node.id)
        if not edges:
            return Outcome(
                status=StageStatus.FAIL,
                message="No outgoing edges to derive choices from",
            )

        choices: list[dict[str, str]] = []
        for e in edges:
            label = e.label or e.target
            accel = _parse_accelerator(label)
            choices.append(
                {
                    "label": label,
                    "target": e.target,
                    "accelerator": accel or "",
                }
            )

        prompt = input.node.attrs.get("prompt", f"Choose next step for {input.node.id}:")

        if self._interviewer is None:
            selected = self._default_choice or (choices[0]["label"] if choices else "")
        else:
            option_labels = [c["label"] for c in choices]
            selected = await self._interviewer.ask(
                str(prompt),
                option_labels,
                timeout=self._timeout or input.node.timeout,
                default=self._default_choice,
            )

        target_ids = []
        for c in choices:
            if c["label"] == selected or c["accelerator"] == selected or c["target"] == selected:
                target_ids.append(c["target"])

        return Outcome(
            status=StageStatus.SUCCESS,
            message=f"Human selected: {selected}",
            suggested_next_ids=target_ids if target_ids else None,
            preferred_label=selected,
        )


def _parse_accelerator(label: str) -> str | None:
    patterns = [
        r"^\[(\w)\]\s*",  # [Y] Label
        r"^(\w)\)\s*",  # Y) Label
        r"^(\w)\s*-\s*",  # Y - Label
    ]
    for pat in patterns:
        m = re.match(pat, label)
        if m:
            return m.group(1).upper()
    return None
