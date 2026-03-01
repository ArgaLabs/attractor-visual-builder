"""Retry logic with exponential backoff and jitter."""

from __future__ import annotations

import asyncio
import random
from typing import Any, Callable, TypeVar

from pydantic import BaseModel

from attractor.llm.errors import ProviderError, SDKError

T = TypeVar("T")


class RetryPolicy(BaseModel):
    max_retries: int = 2
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    on_retry: Callable[..., Any] | None = None

    model_config = {"arbitrary_types_allowed": True}

    def delay_for_attempt(self, attempt: int) -> float:
        delay = self.base_delay * (self.backoff_multiplier**attempt)
        delay = min(delay, self.max_delay)
        if self.jitter:
            delay = delay * random.uniform(0.5, 1.5)
        return delay

    def should_retry(self, error: Exception) -> bool:
        if isinstance(error, ProviderError):
            return error.retryable
        if isinstance(error, SDKError):
            return getattr(error, "retryable", False)
        return True  # unknown errors default retryable


async def retry_async(
    fn: Callable[..., Any],
    policy: RetryPolicy,
    *args: Any,
    **kwargs: Any,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(policy.max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            last_error = e
            if attempt >= policy.max_retries:
                raise
            if not policy.should_retry(e):
                raise

            retry_after: float | None = None
            if isinstance(e, ProviderError) and e.retry_after is not None:
                if e.retry_after > policy.max_delay:
                    raise
                retry_after = e.retry_after

            delay = retry_after if retry_after is not None else policy.delay_for_attempt(attempt)

            if policy.on_retry:
                policy.on_retry(e, attempt, delay)

            await asyncio.sleep(delay)

    if last_error:
        raise last_error
    raise RuntimeError("retry loop ended without result")
