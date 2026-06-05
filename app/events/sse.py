"""SSE streaming helpers for FastAPI."""
import json
from typing import AsyncIterator

from fastapi import Request

from ..core import status as S
from .broadcaster import CandidateEvent, event_hub


def _format_sse(event_name: str, data: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data)}\n\n"


def _terminal(status: str) -> bool:
    return status in S.TERMINAL_STATUSES or status in (S.LEGACY_PROCESSED, S.LEGACY_FAILED)


async def stream_candidate_events(
    candidate_id: int,
    job_id: int | None,
    status: str,
    total_score: float,
    request: Request,
) -> AsyncIterator[str]:
    yield _format_sse(
        "connected",
        {"candidate_id": candidate_id, "job_id": job_id, "message": "subscribed"},
    )

    initial = CandidateEvent(
        candidate_id=candidate_id,
        job_id=job_id,
        status=status,
        terminal=_terminal(status),
        total_score=total_score if total_score else None,
    )
    yield f"event: evaluation_update\ndata: {initial.to_json()}\n\n"

    if _terminal(status):
        yield _format_sse(
            "evaluation_complete",
            {"candidate_id": candidate_id, "status": status},
        )
        return

    async for message in event_hub.subscribe_candidate(candidate_id):
        if await request.is_disconnected():
            break
        yield f"event: evaluation_update\ndata: {message}\n\n"
        data = json.loads(message)
        if data.get("terminal"):
            yield _format_sse(
                "evaluation_complete",
                {"candidate_id": candidate_id, "status": data.get("status")},
            )
            break


async def stream_job_events(job_id: int, request: Request) -> AsyncIterator[str]:
    yield _format_sse("connected", {"job_id": job_id, "message": "subscribed"})

    async for message in event_hub.subscribe_job(job_id):
        if await request.is_disconnected():
            break
        yield f"event: evaluation_update\ndata: {message}\n\n"
