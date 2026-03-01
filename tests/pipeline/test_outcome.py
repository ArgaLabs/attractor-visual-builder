"""Tests for attractor.pipeline.outcome."""

from attractor.pipeline.outcome import Outcome, StageStatus


class TestStageStatus:
    def test_enum_values(self):
        assert StageStatus.SUCCESS.value == "success"
        assert StageStatus.FAIL.value == "fail"
        assert StageStatus.PARTIAL_SUCCESS.value == "partial_success"
        assert StageStatus.SKIPPED.value == "skipped"
        assert StageStatus.PENDING.value == "pending"
        assert StageStatus.RUNNING.value == "running"


class TestOutcome:
    def test_default_construction(self):
        o = Outcome()
        assert o.status == StageStatus.SUCCESS
        assert o.message == ""
        assert o.context_updates == {}
        assert o.preferred_label is None
        assert o.suggested_next_ids is None

    def test_custom_construction(self):
        o = Outcome(
            status=StageStatus.FAIL,
            message="something broke",
            context_updates={"err": True},
            preferred_label="retry",
            suggested_next_ids=["B"],
        )
        assert o.status == StageStatus.FAIL
        assert o.message == "something broke"
        assert o.context_updates == {"err": True}
        assert o.preferred_label == "retry"
        assert o.suggested_next_ids == ["B"]


class TestIsSuccess:
    def test_success(self):
        assert Outcome(status=StageStatus.SUCCESS).is_success is True

    def test_partial_success(self):
        assert Outcome(status=StageStatus.PARTIAL_SUCCESS).is_success is True

    def test_fail_not_success(self):
        assert Outcome(status=StageStatus.FAIL).is_success is False

    def test_skipped_not_success(self):
        assert Outcome(status=StageStatus.SKIPPED).is_success is False


class TestIsFailure:
    def test_fail(self):
        assert Outcome(status=StageStatus.FAIL).is_failure is True

    def test_success_not_failure(self):
        assert Outcome(status=StageStatus.SUCCESS).is_failure is False

    def test_partial_not_failure(self):
        assert Outcome(status=StageStatus.PARTIAL_SUCCESS).is_failure is False
