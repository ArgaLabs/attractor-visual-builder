"""Loop detection for the agentic loop."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def tool_call_signature(name: str, arguments: dict[str, Any]) -> str:
    args_str = json.dumps(arguments, sort_keys=True, default=str)
    h = hashlib.md5((name + args_str).encode()).hexdigest()[:8]
    return f"{name}:{h}"


def detect_loop(signatures: list[str], window_size: int = 10) -> bool:
    if len(signatures) < window_size:
        return False

    recent = signatures[-window_size:]

    for pattern_len in (1, 2, 3):
        if window_size % pattern_len != 0:
            continue
        pattern = recent[:pattern_len]
        all_match = True
        for i in range(pattern_len, window_size, pattern_len):
            if recent[i : i + pattern_len] != pattern:
                all_match = False
                break
        if all_match:
            return True

    return False
