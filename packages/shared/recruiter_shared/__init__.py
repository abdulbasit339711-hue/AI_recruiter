"""Shared, dependency-light utilities used by both the API and the voice agent.

Keeping these in one installable package prevents drift (e.g. the interview-link
token codec and role-slug rules must be identical on both sides).
"""

from .roles import normalize_role_type, KNOWN_ROLE_SLUGS
from .status import (
    QUEUED,
    PROCESSING,
    SHORTLISTED,
    REVIEWED,
    REJECTED,
    UNGRADED,
    ERROR,
    LEGACY_PROCESSED,
    INTERVIEW_ELIGIBLE,
    is_interview_eligible,
)
from .tokens import (
    InviteClaims,
    InviteTokenError,
    mint_invite_token,
    verify_invite_token,
    TOKEN_TYPE,
)

__all__ = [
    "normalize_role_type",
    "KNOWN_ROLE_SLUGS",
    "QUEUED",
    "PROCESSING",
    "SHORTLISTED",
    "REVIEWED",
    "REJECTED",
    "UNGRADED",
    "ERROR",
    "LEGACY_PROCESSED",
    "INTERVIEW_ELIGIBLE",
    "is_interview_eligible",
    "InviteClaims",
    "InviteTokenError",
    "mint_invite_token",
    "verify_invite_token",
    "TOKEN_TYPE",
]
