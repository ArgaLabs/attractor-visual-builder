"""Error hierarchy for the Unified LLM Client."""

from __future__ import annotations

from typing import Any


class SDKError(Exception):
    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message)
        self.cause = cause


class ProviderError(SDKError):
    def __init__(
        self,
        message: str,
        provider: str = "",
        status_code: int | None = None,
        error_code: str | None = None,
        retryable: bool = False,
        retry_after: float | None = None,
        raw: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message, cause)
        self.provider = provider
        self.status_code = status_code
        self.error_code = error_code
        self.retryable = retryable
        self.retry_after = retry_after
        self.raw = raw


class AuthenticationError(ProviderError):
    def __init__(self, **kwargs: Any):
        kwargs.setdefault("retryable", False)
        super().__init__(**kwargs)


class AccessDeniedError(ProviderError):
    def __init__(self, **kwargs: Any):
        kwargs.setdefault("retryable", False)
        super().__init__(**kwargs)


class NotFoundError(ProviderError):
    def __init__(self, **kwargs: Any):
        kwargs.setdefault("retryable", False)
        super().__init__(**kwargs)


class InvalidRequestError(ProviderError):
    def __init__(self, **kwargs: Any):
        kwargs.setdefault("retryable", False)
        super().__init__(**kwargs)


class RateLimitError(ProviderError):
    def __init__(self, **kwargs: Any):
        kwargs.setdefault("retryable", True)
        super().__init__(**kwargs)


class ServerError(ProviderError):
    def __init__(self, **kwargs: Any):
        kwargs.setdefault("retryable", True)
        super().__init__(**kwargs)


class ContentFilterError(ProviderError):
    def __init__(self, **kwargs: Any):
        kwargs.setdefault("retryable", False)
        super().__init__(**kwargs)


class ContextLengthError(ProviderError):
    def __init__(self, **kwargs: Any):
        kwargs.setdefault("retryable", False)
        super().__init__(**kwargs)


class QuotaExceededError(ProviderError):
    def __init__(self, **kwargs: Any):
        kwargs.setdefault("retryable", False)
        super().__init__(**kwargs)


class RequestTimeoutError(SDKError):
    retryable = True


class AbortError(SDKError):
    retryable = False


class NetworkError(SDKError):
    retryable = True


class StreamError(SDKError):
    retryable = True


class InvalidToolCallError(SDKError):
    retryable = False


class NoObjectGeneratedError(SDKError):
    retryable = False


class ConfigurationError(SDKError):
    retryable = False


_STATUS_TO_ERROR: dict[int, type[ProviderError]] = {
    400: InvalidRequestError,
    401: AuthenticationError,
    403: AccessDeniedError,
    404: NotFoundError,
    408: ProviderError,  # mapped as retryable below
    413: ContextLengthError,
    422: InvalidRequestError,
    429: RateLimitError,
    500: ServerError,
    502: ServerError,
    503: ServerError,
    504: ServerError,
}


def error_from_status_code(
    status_code: int,
    message: str,
    provider: str = "",
    error_code: str | None = None,
    raw: dict[str, Any] | None = None,
    retry_after: float | None = None,
) -> ProviderError:
    """Create the appropriate ProviderError subclass from an HTTP status code."""
    msg_lower = message.lower()
    if "context length" in msg_lower or "too many tokens" in msg_lower:
        cls = ContextLengthError
    elif "not found" in msg_lower or "does not exist" in msg_lower:
        cls = NotFoundError
    elif "unauthorized" in msg_lower or "invalid key" in msg_lower:
        cls = AuthenticationError
    elif "content filter" in msg_lower or "safety" in msg_lower:
        cls = ContentFilterError
    else:
        cls = _STATUS_TO_ERROR.get(status_code, ProviderError)

    retryable = status_code in (408, 429, 500, 502, 503, 504)
    if cls not in _STATUS_TO_ERROR.values():
        retryable = True  # unknown errors default retryable

    return cls(
        message=message,
        provider=provider,
        status_code=status_code,
        error_code=error_code,
        retryable=retryable,
        retry_after=retry_after,
        raw=raw,
    )
