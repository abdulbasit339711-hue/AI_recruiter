"""Interview-invite token codec (signed, time-limited).

Used by the API to mint a link when a candidate is shortlisted, and by the voice
service to validate it when the candidate opens the link. Both import THIS module
so the claim shape and signing stay identical.

Validity model (see plan): default short TTL (~10 min) from mint; optionally a
hard ±5-min window around a scheduled ``slot_at`` (nbf = slot-5m, exp = slot+5m).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

import jwt

TOKEN_TYPE = "interview_invite"
_ALGO = "HS256"
_DEFAULT_TTL_MINUTES = 10
_SLOT_WINDOW_SECONDS = 5 * 60
_LEEWAY_SECONDS = 10  # tolerate small clock skew


class InviteTokenError(Exception):
    """Raised when a token is missing, malformed, expired, or not yet valid."""


@dataclass
class InviteClaims:
    candidate_id: int
    job_id: int
    jti: str
    iat: int
    nbf: int
    exp: int
    slot_at: int | None = None


def mint_invite_token(
    candidate_id: int,
    job_id: int,
    secret: str,
    *,
    ttl_minutes: int = _DEFAULT_TTL_MINUTES,
    slot_at: int | None = None,
    now: int | None = None,
) -> str:
    """Create a signed invite token bound to (candidate_id, job_id).

    If ``slot_at`` (unix seconds) is given, the token is valid only within
    ±5 minutes of it; otherwise it is valid for ``ttl_minutes`` from now.
    """
    issued = int(now if now is not None else time.time())
    if slot_at is not None:
        nbf = int(slot_at) - _SLOT_WINDOW_SECONDS
        exp = int(slot_at) + _SLOT_WINDOW_SECONDS
    else:
        nbf = issued
        exp = issued + ttl_minutes * 60

    payload = {
        "typ": TOKEN_TYPE,
        "sub": str(candidate_id),
        "candidate_id": int(candidate_id),
        "job_id": int(job_id),
        "iat": issued,
        "nbf": nbf,
        "exp": exp,
        "jti": uuid.uuid4().hex,
    }
    if slot_at is not None:
        payload["slot_at"] = int(slot_at)
    return jwt.encode(payload, secret, algorithm=_ALGO)


def verify_invite_token(token: str, secret: str) -> InviteClaims:
    """Validate signature + time window + type. Raises InviteTokenError on failure."""
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[_ALGO],
            leeway=_LEEWAY_SECONDS,
            options={"require": ["exp", "nbf", "iat"]},
        )
    except jwt.PyJWTError as e:
        raise InviteTokenError(str(e)) from e

    if payload.get("typ") != TOKEN_TYPE:
        raise InviteTokenError("not an interview-invite token")
    try:
        return InviteClaims(
            candidate_id=int(payload["candidate_id"]),
            job_id=int(payload["job_id"]),
            jti=str(payload.get("jti", "")),
            iat=int(payload["iat"]),
            nbf=int(payload["nbf"]),
            exp=int(payload["exp"]),
            slot_at=int(payload["slot_at"]) if payload.get("slot_at") is not None else None,
        )
    except (KeyError, ValueError, TypeError) as e:
        raise InviteTokenError(f"malformed claims: {e}") from e
