"""Signed, time-limited tokens for the IQ test (stateless — no session table).

Two token types, both HS256 JWTs (mirrors packages/shared tokens.py):

- ``iq_test``   — minted by ``GET /iq-test``. Pins the served question ids (so the
  client can't swap in easier questions) and a short ``exp`` that enforces the
  time limit server-side. Carries NO correct answers.
- ``iq_result`` — minted by ``POST /iq-test/submit`` after server-side scoring.
  Carries the score; ``POST /upload`` verifies it and copies the score onto the
  candidate. Tamper-proof, so the score can safely round-trip through the client.

Secret: ``IQ_TEST_SECRET`` env (falls back to a clearly-labelled dev default, like
the interview-link secret does, so local dev works without configuration).
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass

import jwt

_ALGO = "HS256"
_TEST_TYPE = "iq_test"
_RESULT_TYPE = "iq_result"
_LEEWAY_SECONDS = 10  # tolerate small clock skew
_DEV_SECRET = "dev-iq-secret-change-me"


class IqTokenError(Exception):
    """Raised when a token is missing, malformed, expired, or not yet valid."""


@dataclass
class IqTestClaims:
    job_id: int
    question_ids: list[str]
    iat: int
    exp: int
    jti: str


@dataclass
class IqResultClaims:
    job_id: int
    correct: int
    total: int
    score: float  # time-adjusted percentage 0–100
    time_seconds: int  # server-measured time the candidate took
    detail: list  # per-question breakdown (prompt/options/chosen/correct/time)
    iat: int
    exp: int
    jti: str


def iq_secret() -> str:
    return os.getenv("IQ_TEST_SECRET") or _DEV_SECRET


def mint_test_token(
    job_id: int,
    question_ids: list[str],
    *,
    ttl_seconds: int,
    secret: str | None = None,
    now: int | None = None,
) -> str:
    issued = int(now if now is not None else time.time())
    payload = {
        "typ": _TEST_TYPE,
        "job_id": int(job_id),
        "qids": list(question_ids),
        "iat": issued,
        "exp": issued + int(ttl_seconds),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, secret or iq_secret(), algorithm=_ALGO)


def verify_test_token(token: str, secret: str | None = None) -> IqTestClaims:
    payload = _decode(token, secret)
    if payload.get("typ") != _TEST_TYPE:
        raise IqTokenError("not an iq-test token")
    try:
        return IqTestClaims(
            job_id=int(payload["job_id"]),
            question_ids=[str(q) for q in payload["qids"]],
            iat=int(payload["iat"]),
            exp=int(payload["exp"]),
            jti=str(payload.get("jti", "")),
        )
    except (KeyError, ValueError, TypeError) as e:
        raise IqTokenError(f"malformed claims: {e}") from e


def mint_result_token(
    job_id: int,
    correct: int,
    total: int,
    score: float,
    *,
    time_seconds: int = 0,
    detail: list | None = None,
    ttl_seconds: int,
    secret: str | None = None,
    now: int | None = None,
) -> str:
    issued = int(now if now is not None else time.time())
    payload = {
        "typ": _RESULT_TYPE,
        "job_id": int(job_id),
        "correct": int(correct),
        "total": int(total),
        "score": round(float(score), 2),
        "time_seconds": int(time_seconds),
        "detail": detail or [],
        "iat": issued,
        "exp": issued + int(ttl_seconds),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, secret or iq_secret(), algorithm=_ALGO)


def verify_result_token(token: str, secret: str | None = None) -> IqResultClaims:
    payload = _decode(token, secret)
    if payload.get("typ") != _RESULT_TYPE:
        raise IqTokenError("not an iq-result token")
    try:
        return IqResultClaims(
            job_id=int(payload["job_id"]),
            correct=int(payload["correct"]),
            total=int(payload["total"]),
            score=float(payload["score"]),
            time_seconds=int(payload.get("time_seconds", 0)),
            detail=payload.get("detail") or [],
            iat=int(payload["iat"]),
            exp=int(payload["exp"]),
            jti=str(payload.get("jti", "")),
        )
    except (KeyError, ValueError, TypeError) as e:
        raise IqTokenError(f"malformed claims: {e}") from e


def _decode(token: str, secret: str | None) -> dict:
    try:
        return jwt.decode(
            token,
            secret or iq_secret(),
            algorithms=[_ALGO],
            leeway=_LEEWAY_SECONDS,
            options={"require": ["exp", "iat"]},
        )
    except jwt.PyJWTError as e:
        raise IqTokenError(str(e)) from e
