"""Server-sent event helpers.

Two routes stream to the browser — model pull progress and agent answers — so
the framing lives here rather than being duplicated in both.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    # Nginx buffers proxied responses by default, which defeats streaming.
    "X-Accel-Buffering": "no",
}

#: Proxies and browsers drop a connection that stays silent; a comment line
#: every 15s keeps it open without appearing as an event to the client.
PING_INTERVAL_SECONDS = 15.0


def format_event(event: str, data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def format_ping() -> str:
    return ": ping\n\n"


async def with_ping(
    source: AsyncIterator[str],
    *,
    interval: float = PING_INTERVAL_SECONDS,
) -> AsyncIterator[str]:
    """Interleave keep-alive comments into ``source``.

    ``asyncio.wait_for`` on ``__anext__`` is what makes this possible: the
    generator is pulled in the foreground while a timeout supplies the ticks.
    """
    iterator = source.__aiter__()
    pending: asyncio.Task | None = None

    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(iterator.__anext__())
            try:
                chunk = await asyncio.wait_for(asyncio.shield(pending), timeout=interval)
            except TimeoutError:
                yield format_ping()
                continue
            except StopAsyncIteration:
                return
            pending = None
            yield chunk
    finally:
        if pending is not None and not pending.done():
            pending.cancel()


def sse_response(source: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        with_ping(source),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
