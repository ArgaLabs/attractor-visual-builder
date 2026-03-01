"""Pipeline lifecycle management: start, track, cancel, evict."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from attractor.pipeline.context import Context
from attractor.pipeline.engine import PipelineResult, create_default_registry, run
from attractor.pipeline.events import PipelineEvent, PipelineEventEmitter, PipelineEventType
from attractor.pipeline.graph import Graph
from attractor.pipeline.interviewer import QueueInterviewer
from attractor.pipeline.parser import parse_dot
from attractor.server.models import PipelineInfo, PipelineStatus, QuestionInfo


class ManagedPipeline:
    def __init__(self, pipeline_id: str, graph: Graph, context: Context):
        self.id = pipeline_id
        self.graph = graph
        self.context = context
        self.status = PipelineStatus.PENDING
        self.created_at = time.time()
        self.completed_at: float | None = None
        self.error: str | None = None
        self.current_node: str | None = None
        self.nodes_completed: list[str] = []
        self.result: PipelineResult | None = None
        self.events: list[dict[str, Any]] = []
        self.event_emitter = PipelineEventEmitter()
        self.interviewer = QueueInterviewer()
        self.pending_questions: dict[str, QuestionInfo] = {}
        self._task: asyncio.Task[Any] | None = None
        self._cancelled = False

        self.event_emitter.on(self._on_event)

    def _on_event(self, event: PipelineEvent) -> None:
        ev_dict = {
            "type": event.type.value,
            "timestamp": event.timestamp,
            "data": event.data,
        }
        self.events.append(ev_dict)

        if event.type == PipelineEventType.STAGE_STARTED:
            self.current_node = event.data.get("node_id")
        elif event.type == PipelineEventType.STAGE_COMPLETED:
            node_id = event.data.get("node_id")
            if node_id and node_id not in self.nodes_completed:
                self.nodes_completed.append(node_id)

    def info(self) -> PipelineInfo:
        duration = None
        if self.completed_at:
            duration = self.completed_at - self.created_at
        elif self.status == PipelineStatus.RUNNING:
            duration = time.time() - self.created_at

        return PipelineInfo(
            id=self.id,
            status=self.status,
            name=self.graph.attrs.get("label", ""),
            goal=self.graph.goal,
            nodes_total=len(self.graph.nodes),
            nodes_completed=len(self.nodes_completed),
            current_node=self.current_node,
            created_at=self.created_at,
            duration=duration,
            error=self.error,
        )


class PipelineManager:
    def __init__(self, max_pipelines: int = 100):
        self._pipelines: dict[str, ManagedPipeline] = {}
        self._max_pipelines = max_pipelines

    def get(self, pipeline_id: str) -> ManagedPipeline | None:
        return self._pipelines.get(pipeline_id)

    def list_all(self) -> list[PipelineInfo]:
        return [p.info() for p in self._pipelines.values()]

    async def create_and_run(
        self,
        dot_source: str,
        context_data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> ManagedPipeline:
        if len(self._pipelines) >= self._max_pipelines:
            self._evict_oldest()

        graph = parse_dot(dot_source)
        ctx = Context(context_data or {})
        if graph.goal and "goal" not in ctx.keys():
            ctx.set("goal", graph.goal)

        pipeline_id = f"pipe_{uuid.uuid4().hex[:12]}"
        managed = ManagedPipeline(pipeline_id, graph, ctx)
        self._pipelines[pipeline_id] = managed

        managed.status = PipelineStatus.RUNNING
        managed._task = asyncio.create_task(
            self._run_pipeline(managed, **kwargs)
        )

        return managed

    async def _run_pipeline(
        self, managed: ManagedPipeline, **kwargs: Any
    ) -> None:
        try:
            registry = create_default_registry(
                interviewer=managed.interviewer,
                **kwargs,
            )

            result = await run(
                managed.graph,
                registry=registry,
                context=managed.context,
                events=managed.event_emitter,
                validate=True,
            )

            managed.result = result
            if result.success:
                managed.status = PipelineStatus.COMPLETED
            else:
                managed.status = PipelineStatus.FAILED
                managed.error = "Pipeline execution failed"

        except asyncio.CancelledError:
            managed.status = PipelineStatus.CANCELLED
        except Exception as e:
            managed.status = PipelineStatus.FAILED
            managed.error = str(e)
        finally:
            managed.completed_at = time.time()

    async def cancel(self, pipeline_id: str) -> bool:
        managed = self._pipelines.get(pipeline_id)
        if not managed:
            return False
        if managed._task and not managed._task.done():
            managed._cancelled = True
            managed._task.cancel()
            return True
        return False

    def _evict_oldest(self) -> None:
        completed = [
            (pid, p)
            for pid, p in self._pipelines.items()
            if p.status
            in (
                PipelineStatus.COMPLETED,
                PipelineStatus.FAILED,
                PipelineStatus.CANCELLED,
            )
        ]
        if completed:
            completed.sort(key=lambda x: x[1].created_at)
            oldest_id = completed[0][0]
            del self._pipelines[oldest_id]
