"""Server-Sent Events stream — the client-facing side of the event bus (§34, §59)."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ..events import bus
from ..models import User
from ..rbac import get_current_user

router = APIRouter(prefix="/events", tags=["realtime"])


@router.get("/stream")
async def event_stream(user: User = Depends(get_current_user)):
    async def gen():
        yield f"event: hello\ndata: {json.dumps({'user': user.username})}\n\n"
        heartbeat = 0
        async for message in bus.subscribe():
            yield f"event: {message['event']}\ndata: {json.dumps(message['payload'], ensure_ascii=False)}\n\n"
            heartbeat += 1

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
