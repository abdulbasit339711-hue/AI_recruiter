"""Build an InterviewSession for a specific (candidate, job) at connect time.

This is what makes the agent generic: instead of a hardcoded "Backend Engineer"
session created at startup, the interview is assembled from the Job + Candidate
records in the shared database when the candidate connects.

The per-role questions/goals here are a STUB; Phase 4 replaces `_default_role_config`
with the templates + LLM-fallback role-config service.
"""

from loguru import logger

from database import db_manager
from bot import build_interview_session
from services.role_config_service import build_recruiter_config


class InterviewSetupError(Exception):
    """Raised when the candidate/job can't be resolved for an interview."""


async def create_session_for(candidate_id: int, job_id: int, session_id: str | None = None):
    """Resolve the job + candidate from the shared DB and build an InterviewSession.

    The role-specific questions/goals/system prompt come from the role config
    service (curated templates, with LLM fallback from the job description).

    A caller-supplied ``session_id`` makes the session deterministic per interview link
    so re-opening the same link resumes the SAME session (no new row / no overwrite).
    """
    await db_manager._ensure_pool()

    job = await db_manager.get_job(job_id)
    if not job:
        raise InterviewSetupError(f"job {job_id} not found")
    candidate = await db_manager.get_candidate(candidate_id)
    if not candidate:
        raise InterviewSetupError(f"candidate {candidate_id} not found")

    config = await build_recruiter_config(job, candidate)
    session = build_interview_session(
        candidate_id=candidate_id,
        candidate_name=candidate.get("name"),
        config=config,
        job_id=job_id,
        session_id=session_id,
    )
    logger.info(
        f"[SessionFactory] Built interview for candidate {candidate_id} / job {job_id} "
        f"(role='{config.job_role}')"
    )
    return session
