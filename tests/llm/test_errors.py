"""Tests for attractor.llm.errors."""

from __future__ import annotations

from attractor.llm.errors import (
    AuthenticationError,
    ContentFilterError,
    ContextLengthError,
    InvalidRequestError,
    NotFoundError,
    ProviderError,
    RateLimitError,
    ServerError,
    error_from_status_code,
)

# ---------------------------------------------------------------------------
# error_from_status_code mapping
# ---------------------------------------------------------------------------


class TestErrorFromStatusCode:
    def test_400_maps_to_invalid_request(self):
        err = error_from_status_code(400, "bad request")
        assert isinstance(err, InvalidRequestError)
        assert err.status_code == 400

    def test_401_maps_to_authentication(self):
        err = error_from_status_code(401, "unauthorized")
        assert isinstance(err, AuthenticationError)
        assert err.status_code == 401

    def test_404_maps_to_not_found(self):
        err = error_from_status_code(404, "model not available")
        assert isinstance(err, NotFoundError)
        assert err.status_code == 404

    def test_429_maps_to_rate_limit(self):
        err = error_from_status_code(429, "too many requests")
        assert isinstance(err, RateLimitError)
        assert err.status_code == 429

    def test_500_maps_to_server(self):
        err = error_from_status_code(500, "internal server error")
        assert isinstance(err, ServerError)
        assert err.status_code == 500

    def test_502_maps_to_server(self):
        err = error_from_status_code(502, "bad gateway")
        assert isinstance(err, ServerError)

    def test_503_maps_to_server(self):
        err = error_from_status_code(503, "service unavailable")
        assert isinstance(err, ServerError)

    def test_unknown_status_falls_back_to_provider_error(self):
        err = error_from_status_code(418, "i'm a teapot")
        assert type(err) is ProviderError


# ---------------------------------------------------------------------------
# Retryable flag
# ---------------------------------------------------------------------------


class TestRetryableFlag:
    def test_rate_limit_is_retryable(self):
        err = error_from_status_code(429, "rate limited")
        assert err.retryable is True

    def test_server_error_is_retryable(self):
        err = error_from_status_code(500, "server error")
        assert err.retryable is True

    def test_auth_error_not_retryable(self):
        err = error_from_status_code(401, "bad key")
        assert err.retryable is False

    def test_invalid_request_not_retryable(self):
        err = error_from_status_code(400, "bad request")
        assert err.retryable is False

    def test_not_found_not_retryable(self):
        err = error_from_status_code(404, "gone")
        assert err.retryable is False

    def test_408_is_retryable(self):
        err = error_from_status_code(408, "timeout")
        assert err.retryable is True


# ---------------------------------------------------------------------------
# Message-based classification overrides status code
# ---------------------------------------------------------------------------


class TestMessageClassification:
    def test_context_length_message_overrides_status(self):
        err = error_from_status_code(400, "context length exceeded")
        assert isinstance(err, ContextLengthError)

    def test_too_many_tokens_message(self):
        err = error_from_status_code(400, "too many tokens in request")
        assert isinstance(err, ContextLengthError)

    def test_not_found_message_overrides_status(self):
        err = error_from_status_code(400, "model not found")
        assert isinstance(err, NotFoundError)

    def test_does_not_exist_message(self):
        err = error_from_status_code(400, "resource does not exist")
        assert isinstance(err, NotFoundError)

    def test_unauthorized_message_overrides_status(self):
        err = error_from_status_code(400, "unauthorized access")
        assert isinstance(err, AuthenticationError)

    def test_invalid_key_message(self):
        err = error_from_status_code(400, "invalid key provided")
        assert isinstance(err, AuthenticationError)

    def test_content_filter_message(self):
        err = error_from_status_code(400, "content filter triggered")
        assert isinstance(err, ContentFilterError)

    def test_safety_message(self):
        err = error_from_status_code(400, "safety system blocked")
        assert isinstance(err, ContentFilterError)


# ---------------------------------------------------------------------------
# ProviderError preserves attributes
# ---------------------------------------------------------------------------


class TestProviderErrorAttributes:
    def test_preserves_raw(self):
        raw = {"error": {"type": "invalid_request", "message": "bad"}}
        err = error_from_status_code(400, "bad", raw=raw)
        assert err.raw == raw

    def test_preserves_status_code(self):
        err = error_from_status_code(429, "rate limited")
        assert err.status_code == 429

    def test_preserves_error_code(self):
        err = error_from_status_code(400, "bad", error_code="invalid_model")
        assert err.error_code == "invalid_model"

    def test_preserves_retry_after(self):
        err = error_from_status_code(429, "rate limited", retry_after=5.0)
        assert err.retry_after == 5.0

    def test_preserves_provider(self):
        err = error_from_status_code(500, "server error", provider="openai")
        assert err.provider == "openai"

    def test_error_message_in_str(self):
        err = error_from_status_code(400, "something went wrong")
        assert "something went wrong" in str(err)

    def test_provider_error_direct_construction(self):
        err = ProviderError(
            message="direct",
            provider="test",
            status_code=999,
            error_code="custom",
            retryable=True,
            retry_after=10.0,
            raw={"a": 1},
        )
        assert err.provider == "test"
        assert err.status_code == 999
        assert err.error_code == "custom"
        assert err.retryable is True
        assert err.retry_after == 10.0
        assert err.raw == {"a": 1}
