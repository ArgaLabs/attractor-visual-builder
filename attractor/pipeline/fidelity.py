"""Context fidelity resolution for controlling conversation history size."""

from __future__ import annotations

FIDELITY_MODES = {"full", "truncate", "compact"}
VALID_FIDELITY_PREFIXES = ("summary:",)


def is_valid_fidelity(mode: str) -> bool:
    if mode in FIDELITY_MODES:
        return True
    for prefix in VALID_FIDELITY_PREFIXES:
        if mode.startswith(prefix):
            return True
    return False


def resolve_fidelity(
    edge_fidelity: str | None,
    node_fidelity: str | None,
    graph_fidelity: str | None,
    default: str = "full",
) -> str:
    for f in (edge_fidelity, node_fidelity, graph_fidelity):
        if f is not None and is_valid_fidelity(f):
            return f
    return default


def apply_fidelity(conversation: list[dict], mode: str) -> list[dict]:
    if mode == "full":
        return conversation
    if mode == "truncate":
        max_entries = 20
        if len(conversation) > max_entries:
            return conversation[:2] + conversation[-(max_entries - 2) :]
        return conversation
    if mode == "compact":
        compacted = []
        for entry in conversation:
            role = entry.get("role", "")
            if role == "system":
                compacted.append(entry)
            else:
                text = entry.get("content", "")
                if isinstance(text, str) and len(text) > 200:
                    compacted.append({**entry, "content": text[:200] + "..."})
                else:
                    compacted.append(entry)
        return compacted
    if mode.startswith("summary:"):
        return conversation
    return conversation
