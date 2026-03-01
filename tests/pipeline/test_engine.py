"""Tests for attractor.pipeline.engine.run."""

from attractor.pipeline.checkpoint import Checkpoint
from attractor.pipeline.context import Context
from attractor.pipeline.engine import create_default_registry, run
from attractor.pipeline.handlers.base import HandlerRegistry
from attractor.pipeline.handlers.codergen import CodergenBackend
from attractor.pipeline.outcome import Outcome, StageStatus
from attractor.pipeline.parser import parse_dot


class _MockBackend(CodergenBackend):
    """Backend that always succeeds with a canned message."""

    def __init__(
        self, fail_nodes: set[str] | None = None, fail_counts: dict[str, int] | None = None
    ):
        self._fail_nodes = fail_nodes or set()
        self._fail_counts = fail_counts or {}
        self._call_counts: dict[str, int] = {}

    async def run(self, node_id: str, prompt: str, context: dict) -> Outcome:
        self._call_counts[node_id] = self._call_counts.get(node_id, 0) + 1

        if node_id in self._fail_counts:
            if self._call_counts[node_id] <= self._fail_counts[node_id]:
                return Outcome(
                    status=StageStatus.FAIL, message=f"Fail #{self._call_counts[node_id]}"
                )

        if node_id in self._fail_nodes:
            return Outcome(status=StageStatus.FAIL, message=f"Node {node_id} failed")

        return Outcome(
            status=StageStatus.SUCCESS,
            message=f"Done: {node_id}",
            context_updates={f"{node_id}_done": True},
        )


def _registry(backend=None) -> HandlerRegistry:
    return create_default_registry(backend=backend)


class TestLinearPipeline:
    async def test_start_a_b_exit(self):
        dot = """
        digraph {
            start [shape=point]
            A [shape=box, prompt="step A"]
            B [shape=box, prompt="step B"]
            exit [shape=doublecircle]
            start -> A -> B -> exit
        }
        """
        graph = parse_dot(dot)
        backend = _MockBackend()
        result = await run(graph, registry=_registry(backend), validate=True)

        assert result.success is True
        assert result.execution_order == ["start", "A", "B", "exit"]
        assert result.final_context.get("A_done") is True
        assert result.final_context.get("B_done") is True


class TestConditionalBranching:
    async def test_branch_on_outcome(self):
        dot = """
        digraph {
            start [shape=point]
            decide [shape=diamond]
            good [shape=box, prompt="good path"]
            bad [shape=box, prompt="bad path"]
            exit [shape=doublecircle]
            start -> decide
            decide -> good [condition="outcome=success"]
            decide -> bad [condition="outcome=fail"]
            good -> exit
            bad -> exit
        }
        """
        graph = parse_dot(dot)
        backend = _MockBackend()
        result = await run(graph, registry=_registry(backend), validate=True)

        assert result.success is True
        assert "good" in result.execution_order
        assert "bad" not in result.execution_order


class TestRetryOnFailure:
    async def test_retry_then_succeed(self):
        dot = """
        digraph {
            start [shape=point]
            flaky [shape=box, prompt="flaky op", max_retries="2", backoff_base="0", backoff_max="0"]
            exit [shape=doublecircle]
            start -> flaky -> exit
        }
        """
        graph = parse_dot(dot)
        backend = _MockBackend(fail_counts={"flaky": 1})
        result = await run(graph, registry=_registry(backend), validate=True)

        assert result.success is True
        assert "flaky" in result.execution_order
        assert backend._call_counts["flaky"] == 2

    async def test_retry_exhausted(self):
        dot = """
        digraph {
            start [shape=point]
            flaky [shape=box, prompt="flaky op", max_retries="1", backoff_base="0", backoff_max="0"]
            exit [shape=doublecircle]
            start -> flaky -> exit
        }
        """
        graph = parse_dot(dot)
        backend = _MockBackend(fail_counts={"flaky": 10})
        result = await run(graph, registry=_registry(backend), validate=True)

        assert result.success is False
        assert "exit" not in result.execution_order


class TestGoalGateEnforcement:
    async def test_goal_gate_emits_event_on_failure(self):
        dot = """
        digraph {
            start [shape=point]
            critical [shape=box, prompt="critical", goal_gate="true"]
            exit [shape=doublecircle]
            start -> critical -> exit
        }
        """
        graph = parse_dot(dot)
        events_log = []

        from attractor.pipeline.events import PipelineEventEmitter, PipelineEventType

        emitter = PipelineEventEmitter()
        emitter.on(lambda e: events_log.append(e))

        backend = _MockBackend(fail_nodes={"critical"})
        result = await run(graph, registry=_registry(backend), events=emitter, validate=True)

        assert result.success is False
        gate_events = [e for e in events_log if e.type == PipelineEventType.GOAL_GATE_FAILED]
        assert len(gate_events) == 1


class TestCheckpointSave:
    async def test_checkpoint_saved_after_each_node(self, tmp_path):
        dot = """
        digraph {
            start [shape=point]
            A [shape=box, prompt="a"]
            exit [shape=doublecircle]
            start -> A -> exit
        }
        """
        graph = parse_dot(dot)
        cp_path = str(tmp_path / "checkpoint.json")
        backend = _MockBackend()
        result = await run(
            graph,
            registry=_registry(backend),
            checkpoint_path=cp_path,
            validate=True,
        )

        assert result.success is True
        loaded = Checkpoint.load(cp_path)
        assert loaded.is_completed("start")
        assert loaded.is_completed("A")
        assert loaded.is_completed("exit")


class TestContextFlow:
    async def test_context_updates_flow(self):
        dot = """
        digraph {
            start [shape=point]
            A [shape=box, prompt="a"]
            B [shape=box, prompt="b"]
            exit [shape=doublecircle]
            start -> A -> B -> exit
        }
        """
        graph = parse_dot(dot)
        backend = _MockBackend()
        ctx = Context({"goal": "test"})
        result = await run(graph, registry=_registry(backend), context=ctx, validate=True)

        assert result.final_context.get("A_done") is True
        assert result.final_context.get("B_done") is True
        assert result.final_context.get("goal") == "test"
