import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.auth import token_is_valid
from ..core.jd_embedding_cache import invalidate_job
from ..core.ratelimit import jobs_rate_limit
from ..core.utils import _utcnow
from ..database import get_db
from ..models import Candidate, Job, Org
from ..events.sse import stream_job_events
from ..queue.worker import enqueue_candidate
from ..services.email import OutgoingEmail, get_email_sender

import queue as _queue
from starlette.concurrency import run_in_threadpool
from ..core import status as S

logger = logging.getLogger(__name__)

router = APIRouter()


def _serialize_org(org: Org) -> dict:
    import json as _json
    return {
        "id": org.id,
        "slug": org.slug,
        "name": org.name,
        "primary_color": org.primary_color or "#1C99BF",
        "logo_url": org.logo_url,
        "tagline": org.tagline,
        "about": org.about,
        "contact_email": org.contact_email,
        "social_links": _json.loads(org.social_links) if org.social_links else {},
        "created_at": org.created_at,
    }


def _serialize_job(job: Job, include_private: bool) -> dict:
    """Job payload. `llm_prompt` (the scoring prompt) is admin-only — never expose
    it to unauthenticated applicants, who could otherwise game Tier-3 scoring."""
    data = {
        "id": job.id,
        "title": job.title,
        "department": job.department,
        "job_description": job.job_description,
        "role_type": job.role_type,
        "status": job.status,
        "created_at": job.created_at,
        "org_id": job.org_id,
        "org_slug": job.org.slug if job.org else None,
        "org_name": job.org.name if job.org else None,
        "resume_deadline": job.resume_deadline,
        "interview_deadline": job.interview_deadline,
    }
    if include_private:
        data["llm_prompt"] = job.llm_prompt
        data["tier1_weight"] = job.tier1_weight if job.tier1_weight is not None else 1.0
        data["tier2_weight"] = job.tier2_weight if job.tier2_weight is not None else 1.0
        data["tier3_weight"] = job.tier3_weight if job.tier3_weight is not None else 1.0
    return data


@router.post("/jobs")
def create_job(
    title: str = Query(..., min_length=1, max_length=200),
    department: str = Query(..., min_length=1, max_length=200),
    job_description: str = Query(..., min_length=1, max_length=20000),
    llm_prompt: Optional[str] = Query(None, max_length=10000),
    org_id: Optional[int] = Query(None),
    resume_deadline: Optional[str] = Query(None, max_length=20),
    interview_deadline: Optional[str] = Query(None, max_length=20),
    db: Session = Depends(get_db),
):
    try:
        job = Job(
            title=title,
            department=department,
            job_description=job_description,
            llm_prompt=llm_prompt,
            org_id=org_id,
            resume_deadline=resume_deadline,
            interview_deadline=interview_deadline,
            status="Active",
            created_at=_utcnow().isoformat(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    except Exception:
        db.rollback()
        logger.exception("Database write failed")
        raise HTTPException(status_code=500, detail="Database write failed.")


@router.get("/jobs", dependencies=[Depends(jobs_rate_limit)])
def list_jobs(request: Request, status: Optional[str] = "Active", db: Session = Depends(get_db)):
    is_admin = token_is_valid(request.headers.get("authorization"))
    # Unauthenticated callers (the public careers page) only ever see Active postings.
    query = db.query(Job)
    if is_admin:
        if status:
            query = query.filter(Job.status == status)
    else:
        query = query.filter(Job.status == "Active")
    jobs_list = query.all()
    # Batch-aggregate candidate stats per job in a single query (avoids N+1).
    if jobs_list:
        job_ids = [j.id for j in jobs_list]
        rows = (
            db.query(
                Candidate.job_id,
                func.count(Candidate.id).label("total"),
                func.avg(Candidate.total_score).label("avg_score"),
                func.max(Candidate.total_score).label("top_score"),
            )
            .filter(Candidate.job_id.in_(job_ids))
            .group_by(Candidate.job_id)
            .all()
        )
        stats: dict = {
            r.job_id: {
                "candidate_count": r.total or 0,
                "avg_score": round(float(r.avg_score), 1) if r.avg_score else None,
                "top_score": round(float(r.top_score), 1) if r.top_score else None,
                "shortlisted_count": 0,
            }
            for r in rows
        }
        # Shortlisted count — separate filtered query (cross-DB safe)
        sl_rows = (
            db.query(Candidate.job_id, func.count(Candidate.id))
            .filter(Candidate.job_id.in_(job_ids), Candidate.status == "Shortlisted")
            .group_by(Candidate.job_id)
            .all()
        )
        for job_id, cnt in sl_rows:
            if job_id in stats:
                stats[job_id]["shortlisted_count"] = cnt
    else:
        stats = {}

    return [
        dict(
            **_serialize_job(j, is_admin),
            candidate_count=stats.get(j.id, {}).get("candidate_count", 0),
            avg_score=stats.get(j.id, {}).get("avg_score"),
            top_score=stats.get(j.id, {}).get("top_score"),
            shortlisted_count=stats.get(j.id, {}).get("shortlisted_count", 0),
        )
        for j in jobs_list
    ]


@router.get("/jobs/{job_id}")
def get_job(job_id: int, request: Request, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    is_admin = token_is_valid(request.headers.get("authorization"))
    return _serialize_job(job, is_admin)


@router.get("/jobs/{job_id}/scoring-weights")
def get_scoring_weights(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "tier1_weight": job.tier1_weight if job.tier1_weight is not None else 1.0,
        "tier2_weight": job.tier2_weight if job.tier2_weight is not None else 1.0,
        "tier3_weight": job.tier3_weight if job.tier3_weight is not None else 1.0,
    }


@router.put("/jobs/{job_id}/scoring-weights")
def set_scoring_weights(
    job_id: int,
    tier1_weight: float = Query(1.0, ge=0, le=5),
    tier2_weight: float = Query(1.0, ge=0, le=5),
    tier3_weight: float = Query(1.0, ge=0, le=5),
    db: Session = Depends(get_db),
):
    """Set per-tier scoring multipliers for a job. Applies to FUTURE scoring — reprocess
    the job's candidates (POST /jobs/{id}/reprocess) to recompute existing totals."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    job.tier1_weight = tier1_weight
    job.tier2_weight = tier2_weight
    job.tier3_weight = tier3_weight
    db.commit()
    return {
        "id": job.id,
        "tier1_weight": tier1_weight,
        "tier2_weight": tier2_weight,
        "tier3_weight": tier3_weight,
        "message": "Weights updated. Reprocess this job's candidates to recompute totals.",
    }


@router.put("/jobs/{job_id}")
def update_job(
    job_id: int,
    title: Optional[str] = Query(None, min_length=1, max_length=200),
    department: Optional[str] = Query(None, min_length=1, max_length=200),
    job_description: Optional[str] = Query(None, min_length=1, max_length=20000),
    llm_prompt: Optional[str] = Query(None, max_length=10000),
    status: Optional[str] = Query(None, pattern="^(Active|Archived)$"),
    resume_deadline: Optional[str] = Query(None, max_length=20),
    interview_deadline: Optional[str] = Query(None, max_length=20),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    try:
        if title is not None:
            job.title = title
        if department is not None:
            job.department = department
        if job_description is not None:
            invalidate_job(job.job_description)
            job.job_description = job_description
        if llm_prompt is not None:
            job.llm_prompt = llm_prompt
        if status is not None:
            job.status = status
        if resume_deadline is not None:
            job.resume_deadline = resume_deadline or None
        if interview_deadline is not None:
            job.interview_deadline = interview_deadline or None
        db.commit()
        db.refresh(job)
        return job
    except Exception:
        db.rollback()
        logger.exception("Database update failed")
        raise HTTPException(status_code=500, detail="Database update failed.")


@router.patch("/jobs/{job_id}")
def patch_job(
    job_id: int,
    department: Optional[str] = Query(None, min_length=1, max_length=200),
    job_description: Optional[str] = Query(None, min_length=1, max_length=20000),
    llm_prompt: Optional[str] = Query(None, max_length=10000),
    status: Optional[str] = Query(None, pattern="^(Active|Archived)$"),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    try:
        if department is not None:
            job.department = department
        if job_description is not None:
            invalidate_job(job.job_description)
            job.job_description = job_description
        if llm_prompt is not None:
            job.llm_prompt = llm_prompt
        if status is not None:
            job.status = status
        db.commit()
        db.refresh(job)
        return job
    except Exception:
        db.rollback()
        logger.exception("Database update failed")
        raise HTTPException(status_code=500, detail="Database update failed.")


@router.delete("/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    try:
        invalidate_job(job.job_description)
        db.delete(job)
        db.commit()
        return {"message": "Job and associated candidates deleted.", "job_id": job_id}
    except Exception:
        db.rollback()
        logger.exception("Database delete failed")
        raise HTTPException(status_code=500, detail="Database delete failed.")


@router.get("/jobs/{job_id}/events")
async def job_evaluation_events(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """SSE stream for all candidates under a job (admin leaderboard live updates)."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    async def generate():
        async for chunk in stream_job_events(job_id, request):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/jobs/{job_id}/reprocess")
def reprocess_all_for_job(
    job_id: int,
    limit: int = Query(500, ge=1, le=2000, description="Max candidates to (re)queue in this call"),
    db: Session = Depends(get_db),
):
    """Re-queue a job's candidates in bounded batches.

    Capped at ``limit`` per call (and by the queue's own capacity) so a job with
    thousands of candidates can't time out the request or flood the queue. When
    ``remaining > 0`` the caller can invoke this again to continue.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    total = db.query(Candidate).filter(Candidate.job_id == job_id).count()
    batch = (
        db.query(Candidate)
        .filter(Candidate.job_id == job_id)
        .order_by(Candidate.created_at.asc())
        .limit(limit)
        .all()
    )

    queued = 0
    for cand in batch:
        try:
            enqueue_candidate(cand.id)  # enqueue first so we only mark what we accept
        except _queue.Full:
            break  # queue saturated — stop; the rest can be reprocessed later
        cand.status = S.QUEUED
        queued += 1
    db.commit()  # one commit for the whole batch, not one-per-candidate

    remaining = total - queued
    msg = f"Queued {queued} of {total} candidates for reprocessing."
    if remaining > 0:
        msg += f" {remaining} remaining — call again to continue."
    return {"message": msg, "count": queued, "total": total, "remaining": remaining}


@router.post("/jobs/{job_id}/email")
async def send_shortlist_emails_api(
    job_id: int,
    top_n: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    shortlisted = (
        db.query(Candidate)
        .filter(Candidate.job_id == job_id)
        .filter(Candidate.status.in_([S.SHORTLISTED, "Processed"]))
        .order_by(Candidate.total_score.desc())
        .all()
    )

    if not shortlisted:
        return {"message": "No shortlisted candidates to email.", "failed_count": 0, "errors": []}

    limit = top_n if top_n is not None else len(shortlisted)
    errors: list[str] = []
    messages: list[OutgoingEmail] = []
    for cand in shortlisted[:limit]:
        if not cand.email:
            errors.append(f"{cand.filename}: no email address.")
            continue
        name = cand.name or cand.filename.replace("_", " ")
        messages.append(OutgoingEmail(
            to=cand.email,
            subject=f"Your Application for {job.title} – Shortlisted",
            body=(
                f"Dear {name},\n\n"
                f"You have been shortlisted for {job.title}.\n\n"
                "Our team will contact you shortly.\n\n"
                "Best regards,\nAI Recruiter Team"
            ),
        ))

    # SMTP is blocking I/O over one reused connection — run it off the event loop
    # so a slow mail server can't stall the API.
    send_errors = await run_in_threadpool(get_email_sender().send_batch, messages)
    errors.extend(f"{to}: {err}" for to, err in send_errors.items())

    sent_count = len(messages) - len(send_errors)
    return {
        "message": f"Sent {sent_count} emails.",
        "failed_count": len(errors),
        "errors": errors,
    }
