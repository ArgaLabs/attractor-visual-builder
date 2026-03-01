"""Thread-safe Context key-value store for pipeline execution."""

from __future__ import annotations

import copy
import threading
from typing import Any


class Context:
    def __init__(self, initial: dict[str, Any] | None = None):
        self._data: dict[str, Any] = dict(initial or {})
        self._lock = threading.RLock()

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value

    def update(self, updates: dict[str, Any]) -> None:
        with self._lock:
            self._data.update(updates)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def has(self, key: str) -> bool:
        with self._lock:
            return key in self._data

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._data.keys())

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._data)

    def clone(self) -> Context:
        return Context(self.snapshot())

    def apply_updates(self, updates: dict[str, Any]) -> None:
        self.update(updates)

    def __repr__(self) -> str:
        with self._lock:
            return f"Context({self._data})"
