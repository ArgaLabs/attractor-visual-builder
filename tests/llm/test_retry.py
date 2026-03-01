"""Tests for attractor.llm.retry."""

from __future__ import annotations

import random
from unittest.mock import AsyncMock

import pytest

from attractor.llm.errors import AuthenticationError, RateLimitError
from attractor.llm.retry import RetryPolicy, retry_async

# ---------------------------------------------------------------------------
# RetryPolicy.delay_for_attempt
# ---------------------------------------------------------------------------


class TestDelayForAttempt:
    def test_base_delay_at_attempt_zero(self):
        policy = RetryPolicy(base_delay=1.0, backoff_multiplier=2.0, jitter=False)
        assert policy.delay_for_attempt(0) == 1.0

    def test_exponential_backoff(self):
        policy = RetryPolicy(base_delay=1.0, backoff_multiplier=2.0, jitter=False)
        assert policy.delay_for_attempt(1) == 2.0
        assert policy.delay_for_attempt(2) == 4.0
        assert policy.delay_for_attempt(3) == 8.0

    def test_capped_at_max_delay(self):
        policy = RetryPolicy(base_delay=1.0, backoff_multiplier=2.0, max_delay=5.0, jitter=False)
        assert policy.delay_for_attempt(10) == 5.0

    def test_custom_multiplier(self):
        policy = RetryPolicy(base_delay=0.5, backoff_multiplier=3.0, jitter=False)
        assert policy.delay_for_attempt(0) == 0.5
        assert policy.delay_for_attempt(1) == 1.5
        assert policy.delay_for_attempt(2) == 4.5


class TestJitter:
    def test_jitter_within_bounds(self):
        policy = RetryPolicy(base_delay=10.0, backoff_multiplier=1.0, jitter=True)
        for _ in range(100):
            delay = policy.delay_for_attempt(0)
            assert 5.0 <= delay <= 15.0

    def test_jitter_with_fixed_seed(self):
        policy = RetryPolicy(base_delay=10.0, backoff_multiplier=1.0, jitter=True)
        random.seed(42)
        d1 = policy.delay_for_attempt(0)
        random.seed(42)
        d2 = policy.delay_for_attempt(0)
        assert d1 == d2

    def test_no_jitter_gives_deterministic(self):
        policy = RetryPolicy(base_delay=2.0, backoff_multiplier=2.0, jitter=False)
        assert policy.delay_for_attempt(1) == policy.delay_for_attempt(1)


# ---------------------------------------------------------------------------
# RetryPolicy.should_retry
# ---------------------------------------------------------------------------


class TestShouldRetry:
    def test_retryable_provider_error(self):
        policy = RetryPolicy()
        err = RateLimitError(message="too many requests")
        assert policy.should_retry(err) is True

    def test_non_retryable_provider_error(self):
        policy = RetryPolicy()
        err = AuthenticationError(message="bad key")
        assert policy.should_retry(err) is False

    def test_unknown_exception_defaults_retryable(self):
        policy = RetryPolicy()
        assert policy.should_retry(RuntimeError("boom")) is True


# ---------------------------------------------------------------------------
# retry_async
# ---------------------------------------------------------------------------


class TestRetryAsync:
    async def test_max_retries_zero_means_no_retries(self):
        fn = AsyncMock(side_effect=RateLimitError(message="rate limited"))
        policy = RetryPolicy(max_retries=0, jitter=False)
        with pytest.raises(RateLimitError):
            await retry_async(fn, policy)
        assert fn.call_count == 1

    async def test_succeeds_on_first_try(self):
        fn = AsyncMock(return_value="ok")
        policy = RetryPolicy(max_retries=2, jitter=False)
        result = await retry_async(fn, policy)
        assert result == "ok"
        assert fn.call_count == 1

    async def test_retries_up_to_max(self):
        fn = AsyncMock(
            side_effect=[
                RateLimitError(message="rate limited"),
                RateLimitError(message="rate limited"),
                "success",
            ]
        )
        policy = RetryPolicy(max_retries=2, base_delay=0.001, jitter=False)
        result = await retry_async(fn, policy)
        assert result == "success"
        assert fn.call_count == 3

    async def test_raises_after_max_retries_exhausted(self):
        fn = AsyncMock(side_effect=RateLimitError(message="rate limited"))
        policy = RetryPolicy(max_retries=2, base_delay=0.001, jitter=False)
        with pytest.raises(RateLimitError):
            await retry_async(fn, policy)
        assert fn.call_count == 3

    async def test_non_retryable_raises_immediately(self):
        fn = AsyncMock(side_effect=AuthenticationError(message="bad key"))
        policy = RetryPolicy(max_retries=3, jitter=False)
        with pytest.raises(AuthenticationError):
            await retry_async(fn, policy)
        assert fn.call_count == 1

    async def test_retry_after_overrides_backoff(self):
        err = RateLimitError(message="rate limited", retry_after=0.001)
        fn = AsyncMock(side_effect=[err, "ok"])
        policy = RetryPolicy(max_retries=1, base_delay=100.0, jitter=False)
        result = await retry_async(fn, policy)
        assert result == "ok"

    async def test_retry_after_exceeding_max_delay_raises(self):
        err = RateLimitError(message="rate limited", retry_after=120.0)
        fn = AsyncMock(side_effect=err)
        policy = RetryPolicy(max_retries=2, max_delay=60.0, jitter=False)
        with pytest.raises(RateLimitError):
            await retry_async(fn, policy)
        assert fn.call_count == 1
