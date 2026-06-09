import asyncio
import json
from datetime import date, datetime
from decimal import Decimal
from loguru import logger
from typing import Optional


def _json_default(obj):
    """Serialize types the stdlib json module can't handle.

    Postgres NUMERIC columns (progress_score, average_progress, cost_usd, ...)
    come back as Decimal, which json.dumps rejects; datetimes appear in some
    payloads too. Convert them so broadcasts never fail.
    """
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)


class Broadcaster:
    """
    Manages Server-Sent Events (SSE) connections.
    Allows the bot to push real-time updates to multiple dashboard clients.
    """
    def __init__(self):
        # queue -> session filter. None = unfiltered (dashboard) sees everything;
        # a session_id = candidate page, sees only its own interview + global events.
        self._clients: dict[asyncio.Queue, Optional[str]] = {}

    async def subscribe(self, session_filter: Optional[str] = None) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._clients[queue] = session_filter
        logger.info(f"Client connected (filter={session_filter or 'all'}). Total: {len(self._clients)}")
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        if queue in self._clients:
            del self._clients[queue]
            logger.info(f"Client disconnected. Total: {len(self._clients)}")

    async def broadcast(self, event_type: str, data: dict):
        """Push an event to connected clients, respecting per-session filters.

        An event tagged with a ``session_id`` is delivered only to unfiltered
        clients (the dashboard) and to clients filtered to that exact session — so
        one candidate never sees another candidate's transcript. Events with no
        session_id (participant/status/service) go to everyone.
        """
        if not self._clients:
            logger.debug(f"Broadcasting {event_type} - No clients connected")
            return

        sid = data.get("session_id") if isinstance(data, dict) else None
        message = f"event: {event_type}\ndata: {json.dumps(data, default=_json_default)}\n\n"

        for queue, flt in list(self._clients.items()):
            if flt is None or sid is None or sid == flt:
                await queue.put(message)

# Global broadcaster instance
broadcaster = Broadcaster()
