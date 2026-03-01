"""Tests for attractor.pipeline.interviewer."""

from attractor.pipeline.interviewer import (
    AutoApproveInterviewer,
    QueueInterviewer,
    RecordingInterviewer,
)


class TestAutoApproveInterviewer:
    async def test_returns_first_option(self):
        iv = AutoApproveInterviewer()
        result = await iv.ask("Pick one:", ["alpha", "beta"])
        assert result == "alpha"

    async def test_returns_default_when_provided(self):
        iv = AutoApproveInterviewer()
        result = await iv.ask("Pick one:", ["alpha", "beta"], default="beta")
        assert result == "beta"

    async def test_empty_options_with_default(self):
        iv = AutoApproveInterviewer()
        result = await iv.ask("Pick:", [], default="fallback")
        assert result == "fallback"

    async def test_empty_options_no_default(self):
        iv = AutoApproveInterviewer()
        result = await iv.ask("Pick:", [])
        assert result == ""


class TestQueueInterviewer:
    async def test_returns_enqueued_answers(self):
        qi = QueueInterviewer(["first", "second"])
        assert await qi.ask("Q1:", ["a", "b"]) == "first"
        assert await qi.ask("Q2:", ["a", "b"]) == "second"

    async def test_enqueue_method(self):
        qi = QueueInterviewer()
        qi.enqueue("dynamic")
        assert await qi.ask("Q:", ["a"]) == "dynamic"

    async def test_fallback_to_default_when_empty(self):
        qi = QueueInterviewer()
        result = await qi.ask("Q:", ["a", "b"], default="b")
        assert result == "b"

    async def test_fallback_to_first_option(self):
        qi = QueueInterviewer()
        result = await qi.ask("Q:", ["first", "second"])
        assert result == "first"

    async def test_fallback_empty_options_no_default(self):
        qi = QueueInterviewer()
        result = await qi.ask("Q:", [])
        assert result == ""


class TestRecordingInterviewer:
    async def test_records_interactions(self):
        inner = AutoApproveInterviewer()
        rec = RecordingInterviewer(inner)
        await rec.ask("Q1:", ["a", "b"])
        await rec.ask("Q2:", ["c", "d"], default="d")

        assert len(rec.recordings) == 2
        assert rec.recordings[0]["prompt"] == "Q1:"
        assert rec.recordings[0]["options"] == ["a", "b"]
        assert rec.recordings[0]["selected"] == "a"
        assert rec.recordings[1]["prompt"] == "Q2:"
        assert rec.recordings[1]["selected"] == "d"

    async def test_delegates_to_inner(self):
        qi = QueueInterviewer(["chosen"])
        rec = RecordingInterviewer(qi)
        result = await rec.ask("Q:", ["x", "y"])
        assert result == "chosen"
        assert rec.recordings[0]["selected"] == "chosen"

    async def test_records_default(self):
        inner = AutoApproveInterviewer()
        rec = RecordingInterviewer(inner)
        await rec.ask("Q:", ["a"], default="a")
        assert rec.recordings[0]["default"] == "a"
