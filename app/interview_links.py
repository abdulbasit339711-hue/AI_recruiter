"""Mint & verify time-limited interview-invite links (main API side).

Thin wrapper over recruiter_shared.tokens so the API and the voice service share
the exact same token codec and secret (INTERVIEW_LINK_SECRET).
"""

import os

from recruiter_shared import (
    mint_invite_token,
    verify_invite_token,
    InviteClaims,
    InviteTokenError,
)

__all__ = ["mint_link", "verify_link", "InviteClaims", "InviteTokenError"]


def _secret() -> str:
    secret = os.getenv("INTERVIEW_LINK_SECRET")
    if not secret:
        raise RuntimeError("INTERVIEW_LINK_SECRET is not configured")
    return secret


def mint_link(candidate_id: int, job_id: int, *, ttl_minutes: int | None = None,
              slot_at: int | None = None) -> tuple[str, str]:
    """Return (token, full_url) for a candidate's interview."""
    ttl = ttl_minutes if ttl_minutes is not None else int(os.getenv("INTERVIEW_LINK_TTL_MIN", "10"))
    token = mint_invite_token(candidate_id, job_id, _secret(), ttl_minutes=ttl, slot_at=slot_at)
    base = os.getenv("WEB_BASE_URL", "http://localhost:3000").rstrip("/")
    return token, f"{base}/interview/{token}"


def verify_link(token: str) -> InviteClaims:
    return verify_invite_token(token, _secret())
