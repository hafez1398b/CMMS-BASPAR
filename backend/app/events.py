"""Real-time event layer.

Phase 0/1 ships an in-process asyncio pub/sub bus consumed over SSE.
The interface (`publish` / `subscribe`) is transport-agnostic: when the
deployment grows to multiple application servers the broker is swapped for
Redis Pub/Sub without touching business code (Master-prompt §34/§60).
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncIterator


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def publish(self, event: str, payload: dict | None = None) -> None:
        message = {
            "event": event,
            "payload": payload or {},
            "at": datetime.now(timezone.utc).isoformat(),
        }
        for q in list(self._subscribers):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:  # slow client — drop, do not block writers
                pass

    async def subscribe(self) -> AsyncIterator[dict]:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.add(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subscribers.discard(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


bus = EventBus()
