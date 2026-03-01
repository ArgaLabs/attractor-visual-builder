"""Condition expression language parser and evaluator."""

from __future__ import annotations

from typing import Any

from attractor.pipeline.outcome import Outcome


class ConditionError(Exception):
    pass


def evaluate_condition(
    expr: str,
    outcome: Outcome | None = None,
    context: dict[str, Any] | None = None,
) -> bool:
    expr = expr.strip()
    if not expr:
        return True

    ctx = context or {}

    if "&&" in expr:
        parts = expr.split("&&")
        return all(evaluate_condition(p.strip(), outcome, ctx) for p in parts)

    if "!=" in expr:
        key, _, value = expr.partition("!=")
        key = key.strip()
        value = value.strip()
        actual = _resolve_key(key, outcome, ctx)
        return str(actual).lower() != value.lower()

    if "=" in expr:
        key, _, value = expr.partition("=")
        key = key.strip()
        value = value.strip()
        actual = _resolve_key(key, outcome, ctx)
        return str(actual).lower() == value.lower()

    actual = _resolve_key(expr, outcome, ctx)
    return bool(actual)


def _resolve_key(key: str, outcome: Outcome | None, context: dict[str, Any]) -> Any:
    if key == "outcome":
        return outcome.status.value if outcome else ""
    if key.startswith("context."):
        ctx_key = key[len("context.") :]
        return context.get(ctx_key, "")
    if key.startswith("outcome."):
        attr = key[len("outcome.") :]
        if outcome and hasattr(outcome, attr):
            val = getattr(outcome, attr)
            if hasattr(val, "value"):
                return val.value
            return val
        return ""
    return context.get(key, "")


def parse_condition(expr: str) -> None:
    """Validate condition syntax (raise ConditionError on malformed input)."""
    expr = expr.strip()
    if not expr:
        return

    parts = expr.split("&&")
    for part in parts:
        part = part.strip()
        if not part:
            raise ConditionError(f"Empty clause in condition: {expr!r}")
        if "=" in part:
            sides = part.split("!=") if "!=" in part else part.split("=")
            if len(sides) != 2:
                raise ConditionError(f"Malformed comparison: {part!r}")
            if not sides[0].strip():
                raise ConditionError(f"Empty key in condition: {part!r}")
