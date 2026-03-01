"""Parallel fan-out: concurrent branch execution."""

from __future__ import annotations

import asyncio
from typing import Any

from attractor.pipeline.handlers.base import Handler, HandlerInput
from attractor.pipeline.outcome import Outcome, StageStatus


class ParallelHandler(Handler):
    def __init__(self, branch_executor: Any = None):
        self._branch_executor = branch_executor

    async def execute(self, input: HandlerInput) -> Outcome:
        edges = input.graph.outgoing_edges(input.node.id)
        if not edges:
            return Outcome(status=StageStatus.FAIL, message="No branches to fan out to")

        join_policy = input.node.attrs.get("join_policy", "wait_all")
        error_policy = input.node.attrs.get("error_policy", "fail_fast")
        branch_targets = [e.target for e in edges]

        if self._branch_executor is None:
            results = {
                t: Outcome(status=StageStatus.SUCCESS, message=f"Branch {t} completed")
                for t in branch_targets
            }
        else:
            if error_policy == "fail_fast":
                results = await self._run_fail_fast(branch_targets, input)
            else:
                results = await self._run_continue(branch_targets, input)

        failed = [t for t, o in results.items() if o.is_failure]
        succeeded = [t for t, o in results.items() if o.is_success]

        if error_policy == "fail_fast" and failed:
            return Outcome(
                status=StageStatus.FAIL,
                message=f"Branch(es) failed: {failed}",
                context_updates={
                    "parallel.results": {t: o.model_dump() for t, o in results.items()}
                },
            )

        if join_policy == "first_success" and succeeded:
            return Outcome(
                status=StageStatus.SUCCESS,
                message=f"First successful branch: {succeeded[0]}",
                context_updates={
                    "parallel.results": {t: o.model_dump() for t, o in results.items()}
                },
            )

        overall = (
            StageStatus.SUCCESS
            if not failed
            else (StageStatus.PARTIAL_SUCCESS if succeeded else StageStatus.FAIL)
        )
        return Outcome(
            status=overall,
            message=f"Parallel: {len(succeeded)} succeeded, {len(failed)} failed",
            context_updates={"parallel.results": {t: o.model_dump() for t, o in results.items()}},
        )

    async def _run_fail_fast(self, targets: list[str], input: HandlerInput) -> dict[str, Outcome]:
        results: dict[str, Outcome] = {}
        tasks = {t: asyncio.create_task(self._branch_executor(t, input)) for t in targets}
        try:
            for coro in asyncio.as_completed(tasks.values()):
                result = await coro
                target = next(t for t, task in tasks.items() if task.done() and t not in results)
                results[target] = result
                if result.is_failure:
                    for t, task in tasks.items():
                        if t not in results:
                            task.cancel()
                    break
        except Exception:
            pass
        return results

    async def _run_continue(self, targets: list[str], input: HandlerInput) -> dict[str, Outcome]:
        tasks = {t: asyncio.create_task(self._branch_executor(t, input)) for t in targets}
        await asyncio.gather(*tasks.values(), return_exceptions=True)
        results: dict[str, Outcome] = {}
        for t, task in tasks.items():
            try:
                results[t] = task.result()
            except Exception as e:
                results[t] = Outcome(status=StageStatus.FAIL, message=str(e))
        return results
