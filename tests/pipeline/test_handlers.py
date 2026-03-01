"""Tests for pipeline handlers (async)."""

from attractor.pipeline.context import Context
from attractor.pipeline.graph import Edge, Graph, Node
from attractor.pipeline.handlers.base import HandlerInput
from attractor.pipeline.handlers.codergen import CodergenBackend, CodergenHandler
from attractor.pipeline.handlers.conditional import ConditionalHandler
from attractor.pipeline.handlers.exit import ExitHandler
from attractor.pipeline.handlers.human import WaitForHumanHandler
from attractor.pipeline.handlers.parallel import ParallelHandler
from attractor.pipeline.handlers.start import StartHandler
from attractor.pipeline.handlers.tool import ToolHandler
from attractor.pipeline.interviewer import QueueInterviewer
from attractor.pipeline.outcome import Outcome, StageStatus


def _input(node_attrs=None, context_data=None, edges=None, stage_dir=""):
    node = Node(id="test_node", attrs=node_attrs or {})
    graph = Graph()
    graph.add_node(node)
    for src, tgt, attrs in edges or []:
        graph.add_node(Node(id=tgt))
        graph.add_edge(Edge(source=src, target=tgt, attrs=attrs))
    ctx = Context(context_data or {})
    return HandlerInput(node=node, graph=graph, context=ctx, stage_dir=stage_dir)


class TestStartHandler:
    async def test_returns_success(self):
        handler = StartHandler()
        result = await handler.execute(_input())
        assert result.status == StageStatus.SUCCESS


class TestExitHandler:
    async def test_returns_success(self):
        handler = ExitHandler()
        result = await handler.execute(_input())
        assert result.status == StageStatus.SUCCESS


class TestCodergenHandler:
    async def test_goal_expansion(self, tmp_path):
        handler = CodergenHandler(backend=None)
        inp = _input(
            node_attrs={"prompt": "Build $goal now"},
            context_data={"goal": "the app"},
            stage_dir=str(tmp_path),
        )
        result = await handler.execute(inp)
        assert result.is_success
        prompt_file = tmp_path / "prompt.md"
        assert prompt_file.exists()
        assert "Build the app now" in prompt_file.read_text()

    async def test_writes_response_files(self, tmp_path):
        handler = CodergenHandler(backend=None)
        inp = _input(
            node_attrs={"prompt": "test prompt"},
            stage_dir=str(tmp_path),
        )
        await handler.execute(inp)
        assert (tmp_path / "response.md").exists()
        assert (tmp_path / "status.json").exists()

    async def test_no_backend_gives_simulated(self):
        handler = CodergenHandler(backend=None)
        result = await handler.execute(_input(node_attrs={"prompt": "hello"}))
        assert result.is_success
        assert "Simulated" in result.message

    async def test_backend_returning_outcome(self):
        class MockBackend(CodergenBackend):
            async def run(self, node_id, prompt, context):
                return Outcome(
                    status=StageStatus.SUCCESS,
                    message="backend done",
                    context_updates={"result": "ok"},
                )

        handler = CodergenHandler(backend=MockBackend())
        result = await handler.execute(_input(node_attrs={"prompt": "go"}))
        assert result.status == StageStatus.SUCCESS
        assert result.message == "backend done"
        assert result.context_updates["result"] == "ok"

    async def test_backend_returning_string(self):
        class StringBackend(CodergenBackend):
            async def run(self, node_id, prompt, context):
                return "raw text output"

        handler = CodergenHandler(backend=StringBackend())
        result = await handler.execute(_input(node_attrs={"prompt": "go"}))
        assert result.is_success
        assert result.message == "raw text output"


class TestWaitForHumanHandler:
    async def test_with_queue_interviewer(self):
        qi = QueueInterviewer(["approve"])
        handler = WaitForHumanHandler(interviewer=qi)
        inp = _input(
            edges=[
                ("test_node", "B", {"label": "approve"}),
                ("test_node", "C", {"label": "reject"}),
            ]
        )
        result = await handler.execute(inp)
        assert result.is_success
        assert result.suggested_next_ids == ["B"]
        assert result.preferred_label == "approve"

    async def test_derives_choices_from_edges(self):
        qi = QueueInterviewer(["reject"])
        handler = WaitForHumanHandler(interviewer=qi)
        inp = _input(
            edges=[
                ("test_node", "B", {"label": "approve"}),
                ("test_node", "C", {"label": "reject"}),
            ]
        )
        result = await handler.execute(inp)
        assert result.suggested_next_ids == ["C"]

    async def test_no_edges_returns_fail(self):
        handler = WaitForHumanHandler()
        inp = _input()
        result = await handler.execute(inp)
        assert result.is_failure

    async def test_no_interviewer_uses_default(self):
        handler = WaitForHumanHandler(default_choice="approve")
        inp = _input(
            edges=[
                ("test_node", "B", {"label": "approve"}),
                ("test_node", "C", {"label": "reject"}),
            ]
        )
        result = await handler.execute(inp)
        assert result.is_success
        assert result.preferred_label == "approve"


class TestConditionalHandler:
    async def test_returns_success(self):
        handler = ConditionalHandler()
        result = await handler.execute(_input())
        assert result.status == StageStatus.SUCCESS


class TestToolHandler:
    async def test_missing_command_fails(self):
        handler = ToolHandler()
        result = await handler.execute(_input())
        assert result.is_failure
        assert "command" in result.message.lower()


class TestParallelHandler:
    async def test_fans_out_no_executor(self):
        handler = ParallelHandler(branch_executor=None)
        inp = _input(
            edges=[
                ("test_node", "B", {}),
                ("test_node", "C", {}),
            ]
        )
        result = await handler.execute(inp)
        assert result.is_success

    async def test_no_edges_fails(self):
        handler = ParallelHandler()
        result = await handler.execute(_input())
        assert result.is_failure
