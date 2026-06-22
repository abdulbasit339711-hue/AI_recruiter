"""Candidate evaluation status — a string enum + legacy mapping.

``Status`` is a ``StrEnum`` so members ARE their string value ("Queued", …): they
compare/serialize/persist exactly like the old bare strings (SQLAlchemy String
columns, JSON/SSE, f-strings all behave identically), but typos now fail loudly
and the set of valid statuses is a single source of truth. The module-level
aliases (``QUEUED`` etc.) keep existing ``S.QUEUED`` call sites working unchanged.
"""

from enum import StrEnum


class Status(StrEnum):
    QUEUED = "Queued"
    PROCESSING = "Processing"
    SHORTLISTED = "Shortlisted"
    REVIEWED = "Reviewed"
    REJECTED = "Rejected"
    UNGRADED = "Ungraded"
    ERROR = "Error"


# Backward-compatible module-level aliases (existing code uses `S.QUEUED`, …).
QUEUED = Status.QUEUED
PROCESSING = Status.PROCESSING
SHORTLISTED = Status.SHORTLISTED
REVIEWED = Status.REVIEWED
REJECTED = Status.REJECTED
UNGRADED = Status.UNGRADED
ERROR = Status.ERROR

TERMINAL_STATUSES = frozenset({
    SHORTLISTED,
    REVIEWED,
    REJECTED,
    UNGRADED,
    ERROR,
})

# Legacy statuses from earlier versions
LEGACY_PROCESSED = "Processed"
LEGACY_PENDING = "Pending"
LEGACY_FAILED = "Failed"


def is_shortlisted_for_email(status: str) -> bool:
    return status in (SHORTLISTED, LEGACY_PROCESSED)


def normalize_display_status(status: str) -> str:
    """Map legacy statuses for dashboard backward compatibility."""
    mapping = {
        LEGACY_PROCESSED: SHORTLISTED,
        LEGACY_PENDING: QUEUED,
        LEGACY_FAILED: REJECTED,
    }
    return mapping.get(status, status)
