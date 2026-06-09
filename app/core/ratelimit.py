"""Lightweight in-memory, per-IP rate limiting for public endpoints.

The public apply surface (POST /upload triggers PDF parsing + queued LLM scoring;
GET /jobs is a public read) has no auth, so without a limiter an attacker can spam
requests to run up LLM/Groq cost or exhaust the queue. This is a sliding-window
limiter — good enough as a single-process defense. For multi-instance deployments,
move this to Redis.
"""

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class _SlidingWindow:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max = max_requests
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            dq = self._hits[key]
            cutoff = now - self.window
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if len(dq) >= self.max:
                return False
            dq.append(now)
            # opportunistic cleanup so idle IPs don't accumulate forever
            if len(self._hits) > 10000:
                for k in [k for k, d in self._hits.items() if not d or d[-1] <= cutoff]:
                    self._hits.pop(k, None)
            return True


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(max_requests: int, window_seconds: float = 60.0):
    """Return a FastAPI dependency that enforces max_requests/window per client IP."""
    window = _SlidingWindow(max_requests, window_seconds)

    async def _dep(request: Request) -> None:
        if not window.allow(_client_ip(request)):
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait a moment and try again.",
                headers={"Retry-After": str(int(window_seconds))},
            )

    return _dep


# Configurable limits (per IP). Upload is the expensive one (LLM scoring).
upload_rate_limit = rate_limit(int(os.getenv("UPLOAD_RATE_PER_MIN", "10")), 60.0)
jobs_rate_limit = rate_limit(int(os.getenv("JOBS_RATE_PER_MIN", "120")), 60.0)
