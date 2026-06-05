import asyncio
import json
from loguru import logger
from typing import Set

class Broadcaster:
    """
    Manages Server-Sent Events (SSE) connections.
    Allows the bot to push real-time updates to multiple dashboard clients.
    """
    def __init__(self):
        self._clients: Set[asyncio.Queue] = set()

    async def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue()
        self._clients.add(queue)
        logger.info(f"New dashboard client connected. Total: {len(self._clients)}")
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        if queue in self._clients:
            self._clients.remove(queue)
            logger.info(f"Dashboard client disconnected. Total: {len(self._clients)}")

    async def broadcast(self, event_type: str, data: dict):
        """Pushes an event to all connected dashboard clients."""
        if not self._clients:
            logger.debug(f"Broadcasting {event_type} - No clients connected")
            return

        logger.debug(f"Broadcasting {event_type} to {len(self._clients)} clients: {data}")
        # Prepare SSE format message
        message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        
        # Dispatch to all clients
        for queue in self._clients:
            await queue.put(message)
            logger.debug(f"Event {event_type} put into queue for client")

# Global broadcaster instance
broadcaster = Broadcaster()
