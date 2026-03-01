"""Tests for attractor.pipeline.conditions."""

import pytest

from attractor.pipeline.conditions import ConditionError, evaluate_condition, parse_condition
from attractor.pipeline.outcome import Outcome, StageStatus


class TestOutcomeEquals:
    def test_outcome_success(self):
        o = Outcome(status=StageStatus.SUCCESS)
        assert evaluate_condition("outcome=success", o) is True

    def test_outcome_fail_no_match(self):
        o = Outcome(status=StageStatus.FAIL)
        assert evaluate_condition("outcome=success", o) is False


class TestOutcomeNotEquals:
    def test_not_fail_when_success(self):
        o = Outcome(status=StageStatus.SUCCESS)
        assert evaluate_condition("outcome!=fail", o) is True

    def test_not_fail_when_fail(self):
        o = Outcome(status=StageStatus.FAIL)
        assert evaluate_condition("outcome!=fail", o) is False


class TestContextLookup:
    def test_context_key_equals(self):
        assert evaluate_condition("context.env=prod", None, {"env": "prod"}) is True

    def test_context_key_not_equal(self):
        assert evaluate_condition("context.env=prod", None, {"env": "dev"}) is False


class TestConjunction:
    def test_both_true(self):
        o = Outcome(status=StageStatus.SUCCESS)
        assert (
            evaluate_condition("outcome=success && context.ready=yes", o, {"ready": "yes"}) is True
        )

    def test_one_false(self):
        o = Outcome(status=StageStatus.SUCCESS)
        assert (
            evaluate_condition("outcome=success && context.ready=no", o, {"ready": "yes"}) is False
        )


class TestMissingContextKey:
    def test_missing_key_empty_string(self):
        assert evaluate_condition("context.missing=", None, {}) is True

    def test_missing_key_nonempty_comparison(self):
        assert evaluate_condition("context.missing=something", None, {}) is False


class TestEmptyCondition:
    def test_empty_string_always_true(self):
        assert evaluate_condition("", None) is True

    def test_whitespace_always_true(self):
        assert evaluate_condition("   ", None) is True


class TestBareKey:
    def test_truthy_context_value(self):
        assert evaluate_condition("ready", None, {"ready": "yes"}) is True

    def test_falsy_context_value(self):
        assert evaluate_condition("ready", None, {"ready": ""}) is False

    def test_missing_key_falsy(self):
        assert evaluate_condition("nope", None, {}) is False


class TestParseCondition:
    def test_valid_condition(self):
        parse_condition("outcome=success")

    def test_valid_conjunction(self):
        parse_condition("outcome=success && context.x=y")

    def test_empty_is_valid(self):
        parse_condition("")

    def test_malformed_empty_clause(self):
        with pytest.raises(ConditionError, match="Empty clause"):
            parse_condition("&&")

    def test_malformed_empty_key(self):
        with pytest.raises(ConditionError, match="Empty key"):
            parse_condition("=value")

    def test_bare_key_is_valid(self):
        parse_condition("ready")
