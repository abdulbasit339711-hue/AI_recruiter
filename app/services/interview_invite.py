"""Orchestrate sending an interview invite to a candidate (mint link + email + stamp)."""

import datetime
import logging

from ..interview_links import mint_link
from .email import send_interview_invite

logger = logging.getLogger(__name__)


def invite_candidate(db, candidate, job, *, force: bool = False) -> str | None:
    """Mint an interview link, email it, and record the timestamp.

    Returns the link URL, or None if skipped (no email, or already invited and
    not forced). Best-effort: email failures are logged, not raised.
    """
    if not candidate.email:
        logger.warning("Candidate %s has no email; skipping interview invite", candidate.id)
        return None
    if candidate.interview_invited_at and not force:
        logger.info("Candidate %s already invited at %s; skipping", candidate.id, candidate.interview_invited_at)
        return None

    token, url = mint_link(candidate.id, job.id)
    org = getattr(job, "org", None)
    try:
        send_interview_invite(
            to=candidate.email,
            candidate_name=candidate.name,
            job_title=job.title,
            link=url,
            org_name=org.name if org else None,
            org_color=org.primary_color if org else "#1C99BF",
        )
    except Exception as e:  # noqa: BLE001 - never fail the caller on email issues
        logger.error("Failed to send interview invite to %s: %s", candidate.email, e)

    candidate.interview_invited_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.commit()
    logger.info("Interview invite issued for candidate %s (job %s)", candidate.id, job.id)
    return url
