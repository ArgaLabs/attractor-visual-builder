"""Model catalog for known LLM models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    id: str
    provider: str
    display_name: str = ""
    context_window: int = 0
    max_output: int | None = None
    supports_tools: bool = False
    supports_vision: bool = False
    supports_reasoning: bool = False
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    aliases: list[str] = Field(default_factory=list)


MODELS: list[ModelInfo] = [
    # Anthropic
    ModelInfo(
        id="claude-opus-4-6",
        provider="anthropic",
        display_name="Claude Opus 4.6",
        context_window=200000,
        supports_tools=True,
        supports_vision=True,
        supports_reasoning=True,
        aliases=["opus", "claude-opus"],
    ),
    ModelInfo(
        id="claude-sonnet-4-5",
        provider="anthropic",
        display_name="Claude Sonnet 4.5",
        context_window=200000,
        supports_tools=True,
        supports_vision=True,
        supports_reasoning=True,
        aliases=["sonnet", "claude-sonnet"],
    ),
    # OpenAI
    ModelInfo(
        id="gpt-5.2",
        provider="openai",
        display_name="GPT-5.2",
        context_window=1047576,
        supports_tools=True,
        supports_vision=True,
        supports_reasoning=True,
        aliases=["gpt5"],
    ),
    ModelInfo(
        id="gpt-5.2-mini",
        provider="openai",
        display_name="GPT-5.2 Mini",
        context_window=1047576,
        supports_tools=True,
        supports_vision=True,
        supports_reasoning=True,
        aliases=["gpt5-mini"],
    ),
    ModelInfo(
        id="gpt-5.2-codex",
        provider="openai",
        display_name="GPT-5.2 Codex",
        context_window=1047576,
        supports_tools=True,
        supports_vision=True,
        supports_reasoning=True,
        aliases=["codex"],
    ),
    # Gemini
    ModelInfo(
        id="gemini-3-pro-preview",
        provider="gemini",
        display_name="Gemini 3 Pro (Preview)",
        context_window=1048576,
        supports_tools=True,
        supports_vision=True,
        supports_reasoning=True,
        aliases=["gemini-pro"],
    ),
    ModelInfo(
        id="gemini-3-flash-preview",
        provider="gemini",
        display_name="Gemini 3 Flash (Preview)",
        context_window=1048576,
        supports_tools=True,
        supports_vision=True,
        supports_reasoning=True,
        aliases=["gemini-flash"],
    ),
]

_MODEL_INDEX: dict[str, ModelInfo] = {}
_ALIAS_INDEX: dict[str, ModelInfo] = {}


def _build_index() -> None:
    if _MODEL_INDEX:
        return
    for m in MODELS:
        _MODEL_INDEX[m.id] = m
        for alias in m.aliases:
            _ALIAS_INDEX[alias] = m


def get_model_info(model_id: str) -> ModelInfo | None:
    _build_index()
    return _MODEL_INDEX.get(model_id) or _ALIAS_INDEX.get(model_id)


def list_models(provider: str | None = None) -> list[ModelInfo]:
    _build_index()
    if provider is None:
        return list(MODELS)
    return [m for m in MODELS if m.provider == provider]


def get_latest_model(provider: str, capability: str | None = None) -> ModelInfo | None:
    candidates = list_models(provider)
    if capability:
        attr = f"supports_{capability}"
        candidates = [m for m in candidates if getattr(m, attr, False)]
    return candidates[0] if candidates else None
