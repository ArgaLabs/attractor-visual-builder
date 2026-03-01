"""Start handler - no-op, returns SUCCESS."""

from attractor.pipeline.handlers.base import Handler, HandlerInput
from attractor.pipeline.outcome import Outcome, StageStatus


class StartHandler(Handler):
    async def execute(self, input: HandlerInput) -> Outcome:
        return Outcome(status=StageStatus.SUCCESS, message="Pipeline started")
