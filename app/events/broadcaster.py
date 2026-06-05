"""Thread-safe candidate event hub for SSE (worker thread → asyncio subscribers)."""
import asyncio
import json
import logging
import threading
from dataclasses import asdict, dataclass
from typing import Any, AsyncIterator, Optional

from ..core import status as S

logger = logging.getLogger(__name__)


@dataclass
class CandidateEvent:
    candidate_id: int
    job_id: Optional[int]
    status: str
    event: str = "evaluation_update"
    terminal: bool = False
    total_score: Optional[float] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))


class CandidateEventHub:
    """Publish evaluation lifecycle events; SSE streams subscribe per candidate_id."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queues: dict[int, set[asyncio.Queue[str]]] = {}
        self._job_queues: dict[int, set[asyncio.Queue[str]]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _is_terminal(self, status: str) -> bool:
        return status in S.TERMINAL_STATUSES or status in (
            S.LEGACY_PROCESSED,
            S.LEGACY_FAILED,
        )

    def publish(
        self,
        candidate_id: int,
        status: str,
        job_id: Optional[int] = None,
        total_score: Optional[float] = None,
        event: str = "evaluation_update",
    ) -> None:
        payload = CandidateEvent(
            candidate_id=candidate_id,
            job_id=job_id,
            status=status,
            event=event,
            terminal=self._is_terminal(status),
            total_score=total_score,
        )
        message = payload.to_json()

        with self._lock:
            cand_queues = list(self._queues.get(candidate_id, set()))
            job_queues = list(self._job_queues.get(job_id, set())) if job_id else []

        targets = set(cand_queues) | set(job_queues)
        if not targets:
            logger.debug("No SSE subscribers for candidate %d", candidate_id)
            return

        loop = self._loop
        if loop is None or not loop.is_running():
            logger.warning("Event loop not bound; dropping SSE event for %d", candidate_id)
            return

        for q in targets:
            loop.call_soon_threadsafe(q.put_nowait, message)

        logger.info(
            "SSE event candidate_id=%d status=%s terminal=%s subscribers=%d",
            candidate_id,
            status,
            payload.terminal,
            len(targets),
        )

    async def subscribe_candidate(self, candidate_id: int) -> AsyncIterator[str]:
        q: asyncio.Queue[str] = asyncio.Queue()
        with self._lock:
            self._queues.setdefault(candidate_id, set()).add(q)
        try:
            while True:
                yield await q.get()
        finally:
            with self._lock:
                subs = self._queues.get(candidate_id, set())
                subs.discard(q)
                if not subs:
                    self._queues.pop(candidate_id, None)

    async def subscribe_job(self, job_id: int) -> AsyncIterator[str]:
        q: asyncio.Queue[str] = asyncio.Queue()
        with self._lock:
            self._job_queues.setdefault(job_id, set()).add(q)
        try:
            while True:
                yield await q.get()
        finally:
            with self._lock:
                subs = self._job_queues.get(job_id, set())
                subs.discard(q)
                if not subs:
                    self._job_queues.pop(job_id, None)


event_hub = CandidateEventHub()


def publish_candidate_event(
    candidate_id: int,
    status: str,
    job_id: Optional[int] = None,
    total_score: Optional[float] = None,
    event: str = "evaluation_update",
) -> None:
    event_hub.publish(
        candidate_id=candidate_id,
        status=status,
        job_id=job_id,
        total_score=total_score,
        event=event,
    )
