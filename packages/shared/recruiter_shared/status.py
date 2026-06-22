"""Candidate status constants, shared so the API and voice agent agree.

Mirrors app/core/status.py; the API module should re-export from here over time
to converge on a single definition.
"""

QUEUED = "Queued"
PROCESSING = "Processing"
SHORTLISTED = "Shortlisted"
REVIEWED = "Reviewed"
REJECTED = "Rejected"
UNGRADED = "Ungraded"
ERROR = "Error"

# Legacy alias seen in older data; treated as equivalent to SHORTLISTED.
LEGACY_PROCESSED = "Processed"

#: Statuses that mean "passed screening" and are eligible for an interview invite.
INTERVIEW_ELIGIBLE = frozenset({SHORTLISTED, LEGACY_PROCESSED})


def is_interview_eligible(status: str | None) -> bool:
    return status in INTERVIEW_ELIGIBLE
