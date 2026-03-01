"""Conditional handler - no-op, routing handled by engine edge selection."""

from attractor.pipeline.handlers.base import Handler, HandlerInput
from attractor.pipeline.outcome import Outcome, StageStatus


class ConditionalHandler(Handler):
    async def execute(self, input: HandlerInput) -> Outcome:
        return Outcome(status=StageStatus.SUCCESS, message="Conditional node evaluated")
