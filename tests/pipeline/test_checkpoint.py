"""Tests for attractor.pipeline.checkpoint."""

import json

from attractor.pipeline.checkpoint import Checkpoint, NodeState


class TestSaveLoad:
    def test_json_round_trip(self, tmp_path):
        path = str(tmp_path / "cp.json")
        cp = Checkpoint(
            pipeline_name="test_pipeline",
            current_node_id="A",
            completed_nodes=["start"],
            context_snapshot={"goal": "build"},
            metadata={"version": 1},
        )
        cp.save(path)
        loaded = Checkpoint.load(path)

        assert loaded.pipeline_name == "test_pipeline"
        assert loaded.current_node_id == "A"
        assert loaded.completed_nodes == ["start"]
        assert loaded.context_snapshot == {"goal": "build"}
        assert loaded.metadata == {"version": 1}

    def test_save_creates_directory(self, tmp_path):
        path = str(tmp_path / "subdir" / "cp.json")
        cp = Checkpoint(pipeline_name="test")
        cp.save(path)
        loaded = Checkpoint.load(path)
        assert loaded.pipeline_name == "test"

    def test_saved_format_is_valid_json(self, tmp_path):
        path = str(tmp_path / "cp.json")
        Checkpoint(pipeline_name="test").save(path)
        with open(path) as f:
            data = json.load(f)
        assert "pipeline_name" in data


class TestMarkCompleted:
    def test_mark_completed_adds_to_list(self):
        cp = Checkpoint()
        cp.mark_completed("A")
        assert "A" in cp.completed_nodes

    def test_mark_completed_with_outcome_data(self):
        cp = Checkpoint()
        cp.mark_completed("A", outcome_data={"status": "success"})
        assert cp.node_states["A"].status == "completed"
        assert cp.node_states["A"].outcome_data == {"status": "success"}

    def test_mark_completed_idempotent(self):
        cp = Checkpoint()
        cp.mark_completed("A")
        cp.mark_completed("A")
        assert cp.completed_nodes.count("A") == 1

    def test_node_state_created(self):
        cp = Checkpoint()
        cp.mark_completed("B")
        assert "B" in cp.node_states
        assert isinstance(cp.node_states["B"], NodeState)


class TestIsCompleted:
    def test_completed_true(self):
        cp = Checkpoint()
        cp.mark_completed("X")
        assert cp.is_completed("X") is True

    def test_completed_false(self):
        cp = Checkpoint()
        assert cp.is_completed("X") is False

    def test_multiple_nodes(self):
        cp = Checkpoint()
        cp.mark_completed("A")
        cp.mark_completed("B")
        assert cp.is_completed("A") is True
        assert cp.is_completed("B") is True
        assert cp.is_completed("C") is False
