"""Long-lived asyncio scheduler for recurring pipeline execution."""

from __future__ import annotations

import asyncio
import enum
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from attractor.server.pipeline_manager import PipelineManager

logger = logging.getLogger(__name__)

MAX_INTERVAL_SECONDS = 7 * 24 * 3600   # 7 days
MAX_DURATION_SECONDS = 7 * 24 * 3600   # 7 days
MIN_INTERVAL_SECONDS = 30


class ScheduleStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledPipeline:
    id: str
    dot_source: str
    interval_seconds: int
    expires_at: float
    carry_context: bool
    created_at: float = field(default_factory=time.time)
    status: ScheduleStatus = ScheduleStatus.ACTIVE
    run_count: int = 0
    run_ids: list[str] = field(default_factory=list)
    initial_context: dict[str, Any] | None = None
    last_context: dict[str, Any] | None = None
    _task: asyncio.Task[Any] | None = field(default=None, repr=False)

    @property
    def duration_seconds(self) -> float:
        return self.expires_at - self.created_at

    @property
    def next_run_at(self) -> float | None:
        if self.status != ScheduleStatus.ACTIVE:
            return None
        if self.run_count == 0:
            return self.created_at + self.interval_seconds
        # approximate based on run count
        return self.created_at + self.interval_seconds * (self.run_count + 1)

    def info(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status.value,
            "interval_seconds": self.interval_seconds,
            "duration_seconds": int(self.duration_seconds),
            "carry_context": self.carry_context,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "run_count": self.run_count,
            "run_ids": list(self.run_ids),
            "next_run_at": self.next_run_at,
        }


class Scheduler:
    def __init__(self, pipeline_manager: PipelineManager) -> None:
        self._manager = pipeline_manager
        self._schedules: dict[str, ScheduledPipeline] = {}

    # ── Public API ──────────────────────────────────────────────────────

    async def create(
        self,
        dot_source: str,
        interval_seconds: int,
        duration_seconds: int,
        carry_context: bool = False,
        initial_context: dict[str, Any] | None = None,
    ) -> ScheduledPipeline:
        interval_seconds = max(MIN_INTERVAL_SECONDS, interval_seconds)
        duration_seconds = min(MAX_DURATION_SECONDS, max(interval_seconds, duration_seconds))

        sched_id = f"sched_{uuid.uuid4().hex[:12]}"
        expires_at = time.time() + duration_seconds

        sched = ScheduledPipeline(
            id=sched_id,
            dot_source=dot_source,
            interval_seconds=interval_seconds,
            expires_at=expires_at,
            carry_context=carry_context,
            initial_context=initial_context,
        )
        self._schedules[sched_id] = sched
        sched._task = asyncio.create_task(self._loop(sched_id))
        logger.info(
            "Schedule %s created: every %ds for %ds (carry=%s)",
            sched_id, interval_seconds, duration_seconds, carry_context,
        )
        return sched

    def get(self, schedule_id: str) -> ScheduledPipeline | None:
        return self._schedules.get(schedule_id)

    def list_all(self) -> list[dict[str, Any]]:
        return [s.info() for s in self._schedules.values()]

    async def cancel(self, schedule_id: str) -> bool:
        sched = self._schedules.get(schedule_id)
        if not sched:
            return False
        if sched.status == ScheduleStatus.ACTIVE:
            sched.status = ScheduleStatus.CANCELLED
            if sched._task and not sched._task.done():
                sched._task.cancel()
            logger.info("Schedule %s cancelled", schedule_id)
            return True
        return False

    # ── Internal loop ───────────────────────────────────────────────────

    async def _loop(self, schedule_id: str) -> None:
        sched = self._schedules[schedule_id]
        try:
            while True:
                now = time.time()
                if now >= sched.expires_at:
                    sched.status = ScheduleStatus.COMPLETED
                    logger.info("Schedule %s completed (expired)", schedule_id)
                    return

                # Sleep until next run (or expiry, whichever comes first)
                sleep_for = min(sched.interval_seconds, sched.expires_at - now)
                await asyncio.sleep(sleep_for)

                # Re-check after waking (may have been cancelled during sleep)
                if sched.status != ScheduleStatus.ACTIVE:
                    return
                if time.time() >= sched.expires_at:
                    sched.status = ScheduleStatus.COMPLETED
                    return

                await self._fire(sched)

        except asyncio.CancelledError:
            if sched.status == ScheduleStatus.ACTIVE:
                sched.status = ScheduleStatus.CANCELLED

    async def _fire(self, sched: ScheduledPipeline) -> None:
        """Start one pipeline run for this schedule."""
        context_data: dict[str, Any] = {}

        if sched.carry_context and sched.last_context:
            context_data = dict(sched.last_context)
        elif sched.initial_context:
            context_data = dict(sched.initial_context)

        try:
            managed = await self._manager.create_and_run(
                dot_source=sched.dot_source,
                context_data=context_data or None,
            )
            sched.run_count += 1
            sched.run_ids.append(managed.id)
            logger.info(
                "Schedule %s fired run #%d → pipeline %s",
                sched.id, sched.run_count, managed.id,
            )

            if sched.carry_context:
                # Wait for this run to finish so we can capture its context
                asyncio.create_task(self._capture_context(sched, managed.id))

        except Exception as exc:
            logger.error("Schedule %s fire failed: %s", sched.id, exc)

    async def _capture_context(self, sched: ScheduledPipeline, pipeline_id: str) -> None:
        """Poll until the pipeline finishes, then snapshot its context."""
        from attractor.server.models import PipelineStatus

        terminal = {PipelineStatus.COMPLETED, PipelineStatus.FAILED, PipelineStatus.CANCELLED}
        while True:
            await asyncio.sleep(5)
            managed = self._manager.get(pipeline_id)
            if not managed or managed.status in terminal:
                break

        if managed and managed.status == PipelineStatus.COMPLETED:
            try:
                sched.last_context = managed.context.snapshot()
            except Exception:
                pass
