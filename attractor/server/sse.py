"""SSE (Server-Sent Events) utilities."""

from __future__ import annotations

import asyncio
import json
from typing import Any


def format_sse(event_type: str, data: Any) -> str:
    payload = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"


async def event_stream_generator(
    pipeline_id: str,
    get_events: Any,
    poll_interval: float = 0.5,
    timeout: float = 3600,
) -> Any:
    """Generate SSE events for a pipeline, including history replay."""
    sent_count = 0
    elapsed = 0.0

    while elapsed < timeout:
        events = get_events(pipeline_id)
        if events is None:
            yield format_sse("error", {"message": "Pipeline not found"})
            return

        new_events = events[sent_count:]
        for ev in new_events:
            yield format_sse(ev.get("type", "unknown"), ev)
            sent_count += 1

        last_type = events[-1]["type"] if events else ""
        if last_type in ("pipeline_completed", "pipeline_failed"):
            return

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    yield format_sse("timeout", {"message": "Stream timed out"})
