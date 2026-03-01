"""Tests for attractor.llm.catalog."""

from __future__ import annotations

import pytest

from attractor.llm.catalog import (
    _ALIAS_INDEX,
    _MODEL_INDEX,
    MODELS,
    get_latest_model,
    get_model_info,
    list_models,
)


@pytest.fixture(autouse=True)
def _reset_index():
    """Clear the catalog index between tests so _build_index runs fresh."""
    _MODEL_INDEX.clear()
    _ALIAS_INDEX.clear()
    yield
    _MODEL_INDEX.clear()
    _ALIAS_INDEX.clear()


# ---------------------------------------------------------------------------
# get_model_info
# ---------------------------------------------------------------------------


class TestGetModelInfo:
    def test_by_exact_id(self):
        info = get_model_info("claude-opus-4-6")
        assert info is not None
        assert info.id == "claude-opus-4-6"
        assert info.provider == "anthropic"

    def test_by_alias(self):
        info = get_model_info("opus")
        assert info is not None
        assert info.id == "claude-opus-4-6"

    def test_another_alias(self):
        info = get_model_info("gpt5")
        assert info is not None
        assert info.id == "gpt-5.2"

    def test_gemini_alias(self):
        info = get_model_info("gemini-pro")
        assert info is not None
        assert info.id == "gemini-3-pro-preview"

    def test_unknown_returns_none(self):
        assert get_model_info("nonexistent-model") is None

    def test_returns_model_info_fields(self):
        info = get_model_info("claude-sonnet-4-5")
        assert info is not None
        assert info.display_name == "Claude Sonnet 4.5"
        assert info.context_window == 200000
        assert info.supports_tools is True
        assert info.supports_vision is True
        assert info.supports_reasoning is True


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------


class TestListModels:
    def test_all_models(self):
        models = list_models()
        assert len(models) == len(MODELS)

    def test_filter_by_anthropic(self):
        models = list_models(provider="anthropic")
        assert len(models) >= 2
        assert all(m.provider == "anthropic" for m in models)

    def test_filter_by_openai(self):
        models = list_models(provider="openai")
        assert len(models) >= 3
        assert all(m.provider == "openai" for m in models)

    def test_filter_by_gemini(self):
        models = list_models(provider="gemini")
        assert len(models) >= 2
        assert all(m.provider == "gemini" for m in models)

    def test_filter_unknown_provider(self):
        models = list_models(provider="nonexistent")
        assert len(models) == 0


# ---------------------------------------------------------------------------
# get_latest_model
# ---------------------------------------------------------------------------


class TestGetLatestModel:
    def test_anthropic_latest(self):
        m = get_latest_model("anthropic")
        assert m is not None
        assert m.provider == "anthropic"

    def test_with_tools_capability(self):
        m = get_latest_model("openai", capability="tools")
        assert m is not None
        assert m.supports_tools is True

    def test_with_vision_capability(self):
        m = get_latest_model("gemini", capability="vision")
        assert m is not None
        assert m.supports_vision is True

    def test_with_reasoning_capability(self):
        m = get_latest_model("anthropic", capability="reasoning")
        assert m is not None
        assert m.supports_reasoning is True

    def test_unknown_provider_returns_none(self):
        assert get_latest_model("nonexistent") is None

    def test_impossible_capability_returns_none(self):
        assert get_latest_model("anthropic", capability="teleportation") is None
