"""Integration smoke tests for Pipeline Engine."""

import os

import pytest

from attractor.pipeline.engine import create_default_registry, run
from attractor.pipeline.parser import parse_dot
from attractor.pipeline.validator import validate_or_raise

pytestmark = [pytest.mark.integration]

SIMPLE_PIPELINE = """
digraph test_pipeline {
    graph [goal="Generate a hello world program"]
    start [shape=point]
    generate [shape=box, prompt="Write a Python hello world program for: $goal"]
    review [shape=box, prompt="Review the code and verify it prints hello world"]
    exit [shape=doublecircle]
    start -> generate -> review -> exit
}
"""


async def test_parse_and_validate():
    graph = parse_dot(SIMPLE_PIPELINE)
    assert len(graph.nodes) >= 4
    assert len(graph.edges) >= 3
    assert graph.goal == "Generate a hello world program"

    diagnostics = validate_or_raise(graph)
    errors = [d for d in diagnostics if d.severity.value == "error"]
    assert len(errors) == 0


async def test_execute_with_simulation(tmp_path):
    graph = parse_dot(SIMPLE_PIPELINE)
    registry = create_default_registry()

    result = await run(
        graph,
        registry=registry,
        stage_dir_base=str(tmp_path),
        checkpoint_path=str(tmp_path / "checkpoint.json"),
    )

    assert result.success
    assert "start" in result.execution_order
    assert "generate" in result.execution_order
    assert "review" in result.execution_order
    assert "exit" in result.execution_order

    assert os.path.exists(str(tmp_path / "checkpoint.json"))
    assert os.path.exists(str(tmp_path / "generate" / "prompt.md"))
    assert os.path.exists(str(tmp_path / "generate" / "response.md"))
    assert os.path.exists(str(tmp_path / "generate" / "status.json"))
