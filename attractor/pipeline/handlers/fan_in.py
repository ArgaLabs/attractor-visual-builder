"""Fan-in: consolidates parallel results."""

from __future__ import annotations

from typing import Any

from attractor.pipeline.handlers.base import Handler, HandlerInput
from attractor.pipeline.outcome import Outcome, StageStatus


class FanInHandler(Handler):
    async def execute(self, input: HandlerInput) -> Outcome:
        parallel_results = input.context.get("parallel.results", {})

        if not parallel_results:
            return Outcome(
                status=StageStatus.SUCCESS,
                message="Fan-in: no parallel results to consolidate",
            )

        best_result = heuristic_select(parallel_results)
        return Outcome(
            status=best_result.get("status", StageStatus.SUCCESS),
            message=f"Fan-in selected from {len(parallel_results)} branches",
            context_updates={"fan_in.selected": best_result},
        )


def heuristic_select(results: dict[str, Any]) -> dict[str, Any]:
    status_order = {
        "success": 0,
        "partial_success": 1,
        "fail": 2,
        "skipped": 3,
    }

    ranked = sorted(
        results.items(),
        key=lambda item: status_order.get(
            item[1].get("status", "success") if isinstance(item[1], dict) else "success",
            99,
        ),
    )

    if ranked:
        _, best = ranked[0]
        if isinstance(best, dict):
            return best
    return {"status": "success"}
