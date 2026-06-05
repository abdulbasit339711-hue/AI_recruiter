"""Candidate evaluation status constants and mapping."""

QUEUED = "Queued"
PROCESSING = "Processing"
SHORTLISTED = "Shortlisted"
REVIEWED = "Reviewed"
REJECTED = "Rejected"
UNGRADED = "Ungraded"
ERROR = "Error"

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
