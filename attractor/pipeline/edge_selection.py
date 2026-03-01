"""5-step edge selection algorithm for pipeline execution."""

from __future__ import annotations

import re
from typing import Any

from attractor.pipeline.conditions import evaluate_condition
from attractor.pipeline.graph import Edge
from attractor.pipeline.outcome import Outcome


def _normalize_label(label: str) -> str:
    label = label.strip().lower()
    label = re.sub(r"^\[?\w\]?\s*[-–)]\s*", "", label)
    return label


def select_edge(
    edges: list[Edge],
    outcome: Outcome,
    context: dict[str, Any] | None = None,
) -> Edge | None:
    if not edges:
        return None

    ctx = context or {}

    # Step 1: condition-matching edges
    condition_matches: list[Edge] = []
    unconditional: list[Edge] = []
    for e in edges:
        cond = e.condition
        if cond:
            if evaluate_condition(cond, outcome, ctx):
                condition_matches.append(e)
        else:
            unconditional.append(e)

    if len(condition_matches) == 1:
        return condition_matches[0]

    candidates = condition_matches if condition_matches else unconditional

    if not candidates:
        return None

    # Step 2: preferred_label match
    if outcome.preferred_label:
        normalized_pref = _normalize_label(outcome.preferred_label)
        for e in candidates:
            if _normalize_label(e.label) == normalized_pref:
                return e

    # Step 3: suggested_next_ids match
    if outcome.suggested_next_ids:
        for e in candidates:
            if e.target in outcome.suggested_next_ids:
                return e

    # Step 4: highest weight
    max_weight = max(e.weight for e in candidates)
    if max_weight > 0:
        weighted = [e for e in candidates if e.weight == max_weight]
        if len(weighted) == 1:
            return weighted[0]
        candidates = weighted

    # Step 5: lexical tiebreak
    candidates.sort(key=lambda e: e.target)
    return candidates[0]
