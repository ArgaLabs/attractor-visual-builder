"""Core execution engine: run(), edge selection, goal gates, retry, checkpoints."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from attractor.pipeline.checkpoint import Checkpoint
from attractor.pipeline.context import Context
from attractor.pipeline.edge_selection import select_edge
from attractor.pipeline.events import PipelineEventEmitter, PipelineEventType
from attractor.pipeline.graph import Graph, Node
from attractor.pipeline.handlers.base import Handler, HandlerInput, HandlerRegistry
from attractor.pipeline.handlers.codergen import CodergenHandler
from attractor.pipeline.handlers.conditional import ConditionalHandler
from attractor.pipeline.handlers.exit import ExitHandler
from attractor.pipeline.handlers.fan_in import FanInHandler
from attractor.pipeline.handlers.http import HttpHandler
from attractor.pipeline.handlers.human import WaitForHumanHandler
from attractor.pipeline.handlers.manager import ManagerLoopHandler
from attractor.pipeline.handlers.parallel import ParallelHandler
from attractor.pipeline.handlers.start import StartHandler
from attractor.pipeline.handlers.tool import ToolHandler
from attractor.pipeline.outcome import Outcome, StageStatus
from attractor.pipeline.validator import validate_or_raise


def create_default_registry(**kwargs: Any) -> HandlerRegistry:
    registry = HandlerRegistry()
    registry.register("start", StartHandler())
    registry.register("point", StartHandler())
    registry.register("exit", ExitHandler())
    registry.register("doublecircle", ExitHandler())
    registry.register("codergen", CodergenHandler(backend=kwargs.get("backend")))
    registry.register("box", CodergenHandler(backend=kwargs.get("backend")))
    registry.register(
        "wait.human",
        WaitForHumanHandler(
            interviewer=kwargs.get("interviewer"),
            default_choice=kwargs.get("default_choice"),
        ),
    )
    registry.register("conditional", ConditionalHandler())
    registry.register("diamond", ConditionalHandler())
    registry.register("parallel", ParallelHandler(branch_executor=kwargs.get("branch_executor")))
    registry.register(
        "parallelogram", ParallelHandler(branch_executor=kwargs.get("branch_executor"))
    )
    registry.register("fan_in", FanInHandler())
    registry.register("tool", ToolHandler())
    registry.register("http", HttpHandler())
    registry.register("webhook", HttpHandler())
    registry.register("manager_loop", ManagerLoopHandler())
    return registry


class PipelineResult:
    def __init__(
        self,
        success: bool,
        final_context: dict[str, Any],
        node_outcomes: dict[str, Outcome],
        execution_order: list[str],
    ):
        self.success = success
        self.final_context = final_context
        self.node_outcomes = node_outcomes
        self.execution_order = execution_order


async def run(
    graph: Graph,
    registry: HandlerRegistry | None = None,
    context: Context | None = None,
    checkpoint: Checkpoint | None = None,
    checkpoint_path: str | None = None,
    stage_dir_base: str | None = None,
    events: PipelineEventEmitter | None = None,
    validate: bool = True,
) -> PipelineResult:
    if validate:
        validate_or_raise(graph)

    if registry is None:
        registry = create_default_registry()

    ctx = context or Context({"goal": graph.goal})
    if "goal" not in ctx.keys():
        ctx.set("goal", graph.goal)

    emitter = events or PipelineEventEmitter()
    emitter.emit_simple(PipelineEventType.PIPELINE_STARTED, graph=graph.attrs)

    cp = checkpoint or Checkpoint(pipeline_name=graph.goal)
    node_outcomes: dict[str, Outcome] = {}
    execution_order: list[str] = []

    start_nodes = [
        nid for nid, n in graph.nodes.items() if n.type in ("start", "point") and nid == "start"
    ]
    if not start_nodes:
        start_nodes = [nid for nid, n in graph.nodes.items() if n.type in ("start", "point")]

    current_node_id = start_nodes[0] if start_nodes else None

    if cp.completed_nodes and cp.current_node_id:
        current_node_id = cp.current_node_id
        ctx.apply_updates(cp.context_snapshot)

    while current_node_id:
        node = graph.node(current_node_id)
        if node is None:
            break

        if cp.is_completed(current_node_id) and current_node_id != cp.current_node_id:
            edges = graph.outgoing_edges(current_node_id)
            prev_outcome = node_outcomes.get(current_node_id, Outcome())
            edge = select_edge(edges, prev_outcome, ctx.snapshot())
            current_node_id = edge.target if edge else None
            continue

        emitter.emit_simple(PipelineEventType.STAGE_STARTED, node_id=current_node_id)

        handler = registry.get(node.type)
        if handler is None:
            handler = registry.get("codergen")
        if handler is None:
            node_outcomes[current_node_id] = Outcome(
                status=StageStatus.FAIL,
                message=f"No handler for type '{node.type}'",
            )
            break

        stage_dir = ""
        if stage_dir_base:
            stage_dir = os.path.join(stage_dir_base, current_node_id)

        outcome = await _execute_with_retry(handler, node, graph, ctx, stage_dir, emitter)

        node_outcomes[current_node_id] = outcome
        execution_order.append(current_node_id)

        if outcome.context_updates:
            ctx.apply_updates(outcome.context_updates)

        cp.mark_completed(current_node_id, outcome.model_dump())
        cp.context_snapshot = ctx.snapshot()

        if checkpoint_path:
            cp.save(checkpoint_path)

        emitter.emit_simple(
            PipelineEventType.STAGE_COMPLETED,
            node_id=current_node_id,
            status=outcome.status.value,
        )

        is_exit = node.type in ("exit", "doublecircle") or node.id in ("exit", "end")
        if is_exit:
            break

        if outcome.is_failure:
            next_id = _handle_failure_routing(node, graph)
            if next_id:
                current_node_id = next_id
                continue
            break

        edges = graph.outgoing_edges(current_node_id)
        if not edges:
            break

        edge = select_edge(edges, outcome, ctx.snapshot())
        if edge is None:
            break

        if edge.loop_restart:
            current_node_id = start_nodes[0] if start_nodes else None
            continue

        current_node_id = edge.target
        cp.current_node_id = current_node_id

    _enforce_goal_gates(graph, node_outcomes, ctx, emitter)

    all_success = all(
        o.is_success
        for nid, o in node_outcomes.items()
        if graph.node(nid) and graph.node(nid).type not in ("start", "point")  # type: ignore[union-attr]
    )

    emitter.emit_simple(PipelineEventType.PIPELINE_COMPLETED, success=all_success)

    return PipelineResult(
        success=all_success,
        final_context=ctx.snapshot(),
        node_outcomes=node_outcomes,
        execution_order=execution_order,
    )


async def _execute_with_retry(
    handler: Handler,
    node: Node,
    graph: Graph,
    ctx: Context,
    stage_dir: str,
    emitter: PipelineEventEmitter,
) -> Outcome:
    max_retries = node.max_retries
    backoff_base = float(node.attrs.get("backoff_base", 1.0))
    backoff_max = float(node.attrs.get("backoff_max", 60.0))
    attempt = 0

    while True:
        input_data = HandlerInput(node=node, graph=graph, context=ctx, stage_dir=stage_dir)
        try:
            outcome = await handler.execute(input_data)
        except Exception as e:
            outcome = Outcome(
                status=StageStatus.FAIL,
                message=f"Handler exception: {e}",
            )

        if outcome.auto_status or outcome.status == StageStatus.PENDING:
            outcome.status = StageStatus.SUCCESS
            outcome.auto_status = True

        if outcome.is_success:
            return outcome

        if attempt >= max_retries:
            if node.allow_partial:
                outcome.status = StageStatus.PARTIAL_SUCCESS
            return outcome

        attempt += 1
        delay = min(backoff_base * (2 ** (attempt - 1)), backoff_max)
        emitter.emit_simple(
            PipelineEventType.STAGE_RETRY,
            node_id=node.id,
            attempt=attempt,
            delay=delay,
        )
        await asyncio.sleep(delay)


def _handle_failure_routing(node: Node, graph: Graph) -> str | None:
    if node.retry_target:
        target = graph.node(node.retry_target)
        if target:
            return node.retry_target

    if node.fallback_retry_target:
        target = graph.node(node.fallback_retry_target)
        if target:
            return node.fallback_retry_target

    fail_edges = [e for e in graph.outgoing_edges(node.id) if "fail" in e.label.lower()]
    if fail_edges:
        return fail_edges[0].target

    return None


def _enforce_goal_gates(
    graph: Graph,
    outcomes: dict[str, Outcome],
    ctx: Context,
    emitter: PipelineEventEmitter,
) -> None:
    for nid, node in graph.nodes.items():
        if not node.goal_gate:
            continue
        outcome = outcomes.get(nid)
        if outcome and not outcome.is_success:
            emitter.emit_simple(
                PipelineEventType.GOAL_GATE_FAILED,
                node_id=nid,
                status=outcome.status.value if outcome else "missing",
            )
