"""Optional HTTP server mode with SSE event streaming."""

from __future__ import annotations

import asyncio
import json
from typing import Any


class PipelineServer:
    """Lightweight HTTP server that streams pipeline events via SSE.

    Requires an ASGI framework (e.g., starlette) for production use.
    This module provides the core SSE streaming logic.
    """

    def __init__(self) -> None:
        self._event_queues: list[asyncio.Queue[dict[str, Any]]] = []
        self._running = False

    def broadcast(self, event: dict[str, Any]) -> None:
        for queue in self._event_queues:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def create_event_handler(self) -> Any:
        def handler(event: Any) -> None:
            data = event.model_dump() if hasattr(event, "model_dump") else {"type": str(event)}
            self.broadcast(data)

        return handler

    async def event_stream(self) -> Any:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self._event_queues.append(queue)
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event, default=str)}\n\n"
        finally:
            self._event_queues.remove(queue)

    async def start(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False
