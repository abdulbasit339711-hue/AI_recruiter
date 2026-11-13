import json
import logging
import queue as _queue
from datetime import datetime, timezone
from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core import status as S
from ..core.ratelimit import upload_rate_limit
from ..core.utils import _utcnow
from ..core.local_only import is_local_only
from ..database import config, get_db
from ..events import publish_candidate_event
from ..events.sse import stream_candidate_events
from ..intake.upload import validate_and_extract, IngestionError
from ..iq import IqTokenError
from ..iq.attach import attach_iq_result
from ..models import Candidate, Job
from ..queue.worker import enqueue_candidate
from ..schemas import (
    CandidateResponse,
    NoteRequest,
    ScoreOverrideRequest,
    StatusUpdateRequest,
    TimelineEntry,
    TimelineResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _load_status_history(candidate) -> list:
    """Parse a candidate's status_history JSON, *preserving* unreadable data.

    The old code silently swallowed a JSON error and reset history to ``[]`` —
    the next write then overwrote the column, permanently losing the audit trail.
    Here, corrupt/non-list data is wrapped into a 'recovered' entry instead of
    being dropped, and the problem is logged.
    """
    raw = candidate.status_history
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
        logger.warning("status_history for candidate %s is not a list; preserving it.", candidate.id)
    except Exception:
        logger.warning("status_history for candidate %s is unreadable; preserving it.", candidate.id)
    return [{
        "type": "recovered",
        "status": "",
        "changed_by": "system",
        "changed_at": _utcnow().isoformat() + "Z",
        "note": "Previous status history was unreadable and has been preserved.",
        "raw": str(raw)[:2000],
    }]


@router.post("/upload", dependencies=[Depends(upload_rate_limit)])
async def upload_resume(
    job_id: int = Query(..., description="Target Job ID"),
    file: UploadFile = File(...),
    iq_token: Optional[str] = Form(None, description="Signed IQ result token (optional)"),
    consent: bool = Form(False, description="Applicant ticked the AI-processing consent box"),
    db: Session = Depends(get_db),
):
    """
    Validates PDF, stores candidate as Queued, enqueues background evaluation.
    Returns immediately (~50-100ms target excluding file read).
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    if job.status == "Archived":
        raise HTTPException(status_code=400, detail=f"Job '{job.title}' is archived.")

    try:
        file_bytes = await file.read()
        filename = file.filename or "resume.pdf"
        raw_text = validate_and_extract(file_bytes, filename)

        candidate = Candidate(
            filename=filename,
            raw_text=raw_text,
            job_id=job_id,
            status=S.QUEUED,
            created_at=_utcnow().isoformat(),
            consent_at=_utcnow().isoformat() if consent else None,
        )
        # Attach the IQ screen result if a valid token was supplied. This NEVER
        # blocks the application: an absent/invalid/mismatched token simply leaves
        # the IQ score null.
        if iq_token:
            try:
                why = attach_iq_result(db, candidate, iq_token, job_id)
                if why:
                    logger.warning("IQ token ignored on upload: %s", why)
            except IqTokenError as e:
                logger.warning("Ignoring invalid IQ token on upload: %s", e)
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        try:
            enqueue_candidate(candidate.id)
        except _queue.Full:
            candidate.status = S.ERROR
            candidate.summary = "Evaluation queue is full; please retry shortly."
            db.commit()
            raise HTTPException(status_code=503, detail="Server is busy. Please retry in a moment.")

        publish_candidate_event(
            candidate.id,
            S.QUEUED,
            job_id=job_id,
            event="queued",
        )

        # Note: no interview link is minted here. Interview invites are sent only from
        # the HR admin dashboard (POST /candidates/{id}/interview-invite) after review —
        # never self-service from the applicant upload flow.
        return {
            "id": candidate.id,
            "filename": candidate.filename,
            "job_id": candidate.job_id,
            "status": candidate.status,
            "message": "Resume queued for evaluation.",
        }

    except IngestionError as ie:
        raise HTTPException(status_code=ie.status_code, detail=str(ie))
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail="Upload failed.")


@router.get("/jobs/{job_id}/candidates")
def list_candidates(
    job_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None, description="Filter by candidate status"),
    hr_status: Optional[str] = Query(None, description="Filter by specific HR status"),
    sort_by: str = Query("total_score", description="Field to sort by"),
    order: str = Query("desc", description="Sort order (asc/desc)"),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    query = db.query(Candidate).filter(Candidate.job_id == job_id)
    if status:
        query = query.filter(Candidate.status == status)
    if hr_status:
        query = query.filter(Candidate.hr_status == hr_status)

    # Sorting logic
    sort_column = Candidate.total_score
    if sort_by == "created_at":
        sort_column = Candidate.created_at
    elif sort_by == "hr_status":
        sort_column = Candidate.hr_status
    elif sort_by == "total_score":
        # Effective score: use hr_score_override if set, otherwise total_score
        sort_column = func.coalesce(Candidate.hr_score_override, Candidate.total_score)

    if order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    total = query.count()
    candidates = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": candidates,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": ceil(total / page_size) if total else 0,
    }


@router.get("/candidates/{candidate_id}")
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return candidate


@router.get("/candidates/{candidate_id}/resume", response_class=PlainTextResponse)
def get_candidate_resume(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if not candidate.raw_text:
        raise HTTPException(status_code=404, detail="Resume text not found.")
    return PlainTextResponse(
        candidate.raw_text,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'inline; filename="{candidate.filename}.txt"'},
    )


@router.patch("/candidates/{candidate_id}/status", response_model=CandidateResponse)
def update_candidate_status(
    candidate_id: int,
    payload: StatusUpdateRequest,
    db: Session = Depends(get_db),
):
    # Lock the row for the transaction so concurrent PATCHes don't lose status_history
    # entries (read-modify-write of the JSON list). No-op on SQLite (tests).
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).with_for_update().first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    history = _load_status_history(candidate)

    new_entry = {
        "type": "status_change",
        "status": payload.hr_status,
        "changed_by": payload.changed_by,
        "changed_at": _utcnow().isoformat() + "Z",
        "note": payload.note
    }
    history.append(new_entry)

    candidate.hr_status = payload.hr_status
    candidate.status_history = json.dumps(history)

    try:
        db.commit()
        db.refresh(candidate)
        return candidate
    except Exception:
        db.rollback()
        logger.exception("Database update failed")
        raise HTTPException(status_code=500, detail="Database update failed.")


@router.post("/candidates/{candidate_id}/notes", response_model=CandidateResponse)
def add_candidate_note(
    candidate_id: int,
    payload: NoteRequest,
    db: Session = Depends(get_db),
):
    # Lock the row so concurrent note appends don't clobber each other.
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).with_for_update().first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    timestamp_str = _utcnow().strftime("%Y-%m-%d %H:%M UTC")
    formatted_note = f"[{timestamp_str}] {payload.author}: {payload.note}"

    if candidate.hr_notes:
        candidate.hr_notes = f"{candidate.hr_notes}\n{formatted_note}"
    else:
        candidate.hr_notes = formatted_note

    try:
        db.commit()
        db.refresh(candidate)
        return candidate
    except Exception:
        db.rollback()
        logger.exception("Database update failed")
        raise HTTPException(status_code=500, detail="Database update failed.")


@router.patch("/candidates/{candidate_id}/score-override", response_model=CandidateResponse)
def override_candidate_score(
    candidate_id: int,
    payload: ScoreOverrideRequest,
    db: Session = Depends(get_db),
):
    # Lock the row so a concurrent status PATCH doesn't drop this override's history entry.
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).with_for_update().first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    history = _load_status_history(candidate)

    new_entry = {
        "type": "score_override",
        "status": f"Score Overridden: {payload.override_score}",
        "changed_by": payload.changed_by,
        "changed_at": _utcnow().isoformat() + "Z",
        "note": payload.reason
    }
    history.append(new_entry)

    candidate.hr_score_override = payload.override_score
    candidate.status_history = json.dumps(history)

    try:
        db.commit()
        db.refresh(candidate)
        return candidate
    except Exception:
        db.rollback()
        logger.exception("Database update failed")
        raise HTTPException(status_code=500, detail="Database update failed.")


@router.get("/candidates/{candidate_id}/timeline", response_model=TimelineResponse)
def get_candidate_timeline(
    candidate_id: int,
    db: Session = Depends(get_db),
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    history = _load_status_history(candidate)

    entries = []
    for entry in history:
        entries.append(
            TimelineEntry(
                type=entry.get("type", "status_change"),
                status=str(entry.get("status", "")),
                changed_by=entry.get("changed_by", ""),
                changed_at=entry.get("changed_at", ""),
                note=entry.get("note", None)
            )
        )

    entries.sort(key=lambda x: x.changed_at)
    return TimelineResponse(timeline=entries)


@router.get("/candidates/{candidate_id}/events")
async def candidate_evaluation_events(
    candidate_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    SSE stream for a single applicant/candidate.
    Emits candidate_id + status; client should GET /candidates/{id} when terminal.
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    async def generate():
        async for chunk in stream_candidate_events(
            candidate_id,
            candidate.job_id,
            candidate.status,
            candidate.total_score or 0.0,
            request,
        ):
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


@router.post("/candidates/{candidate_id}/reprocess")
def reprocess_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    candidate.status = S.QUEUED
    db.commit()
    try:
        enqueue_candidate(candidate_id)
    except _queue.Full:
        raise HTTPException(status_code=503, detail="Server is busy. Please retry in a moment.")
    db.refresh(candidate)
    return {
        "id": candidate.id,
        "status": candidate.status,
        "message": "Reprocessing queued.",
    }


@router.post("/candidates/{candidate_id}/resume", dependencies=[Depends(upload_rate_limit)])
async def replace_candidate_resume(
    candidate_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Attach or replace a candidate's résumé PDF, then re-score them.

    Lets HR give a résumé to a candidate created without one, or swap in a corrected
    file — reusing the same extraction + scoring pipeline as /upload."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    try:
        file_bytes = await file.read()
        filename = file.filename or "resume.pdf"
        raw_text = validate_and_extract(file_bytes, filename)
    except IngestionError as ie:
        raise HTTPException(status_code=ie.status_code, detail=str(ie))

    candidate.filename = filename
    candidate.raw_text = raw_text
    candidate.status = S.QUEUED
    db.commit()
    try:
        enqueue_candidate(candidate_id)
    except _queue.Full:
        raise HTTPException(status_code=503, detail="Server is busy. Please retry in a moment.")
    db.refresh(candidate)
    publish_candidate_event(candidate.id, S.QUEUED, job_id=candidate.job_id, event="queued")
    return {
        "id": candidate.id,
        "filename": candidate.filename,
        "status": candidate.status,
        "message": "Résumé attached; re-scoring queued.",
    }


@router.get("/candidates/{candidate_id}/score-explanation")
def score_explanation(candidate_id: int, db: Session = Depends(get_db)):
    """Plain-language breakdown of why a candidate scored what they did (HR view).

    Tier 1 is itemised by re-running the deterministic rules on the stored résumé text;
    Tier 2/3 are explained from stored values (matched/missing skills and evidence are
    already on the candidate record)."""
    cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    job = db.query(Job).filter(Job.id == cand.job_id).first()
    cfg, pipe = config.get("scoring", {}), config.get("pipeline", {})
    weight = lambda n: (getattr(job, f"tier{n}_weight", None) or 1.0) if job else 1.0  # noqa: E731

    items = None
    if cand.raw_text:
        try:
            from ..scoring.tier1 import score_tier1
            t1 = score_tier1(cand.raw_text)
            items = [
                {"label": label, "points": float(t1.get(key) or 0.0), "max": float(cfg.get(wkey, dflt))}
                for label, key, wkey, dflt in (
                    ("Email address found", "email_score", "email_weight", 5),
                    ("Phone number found", "phone_score", "phone_weight", 5),
                    ("Education section present", "education_score", "education_weight", 7),
                    ("Experience section present", "experience_score", "experience_weight", 7),
                    ("Skills section present", "skills_score", "skills_weight", 6),
                )
            ]
        except Exception as e:  # noqa: BLE001 — explanation is best-effort; never fail the page
            logger.warning("Tier-1 itemisation unavailable for candidate %s: %s", candidate_id, e)

    try:
        t3_data = json.loads(cand.evaluation_data) if cand.evaluation_data else {}
    except ValueError:
        t3_data = {}
    ungraded = cand.status == S.UNGRADED
    if ungraded and is_local_only():
        t3_note = "AI evaluation was skipped: the system runs in local-only mode (no data sent to external AI)."
    elif ungraded:
        t3_note = (
            f"AI evaluation was not run: it only runs when Tier 1 + Tier 2 reaches "
            f"{pipe.get('tier3_combined_threshold', 25.0)} (this résumé: {(cand.tier1 or 0) + (cand.tier2 or 0):.1f})."
        )
    elif t3_data.get("is_fallback"):
        t3_note = "The AI service was unavailable, so a keyword-overlap estimate was used instead. Treat this part as low confidence."
    else:
        t3_note = "An AI model compared the résumé with the job description (see summary, evidence and skills below)."

    shortlist_min = float(pipe.get("shortlisted_min_score", 75.0))
    review_min = float(pipe.get("reviewed_min_score", 60.0))
    total = cand.total_score or 0.0
    if total >= shortlist_min:
        outcome = f"Total {total:.1f} is at or above the shortlist threshold ({shortlist_min:g})."
    elif total >= review_min:
        outcome = f"Total {total:.1f} is at or above the review threshold ({review_min:g}) but below shortlist ({shortlist_min:g})."
    elif ungraded:
        outcome = f"Total {total:.1f} — not graded by AI; below the review threshold ({review_min:g}) on Tier 1 + 2 alone."
    else:
        outcome = f"Total {total:.1f} is below the review threshold ({review_min:g}); the AI's own recommendation then decides the status."

    try:
        warnings = json.loads(cand.warnings) if cand.warnings else []
    except ValueError:
        warnings = []
    return {
        "total": total,
        "override": cand.hr_score_override,
        "status": cand.status,
        "outcome": outcome,
        "tiers": [
            {"key": "tier1", "label": "Profile rules", "score": cand.tier1 or 0.0, "max": 30, "weight": weight(1),
             "note": "Checks the résumé has contact details and the standard sections.", "items": items},
            {"key": "tier2", "label": "Match to job description", "score": cand.tier2 or 0.0, "max": float(cfg.get("semantic_weight", 40)),
             "weight": weight(2), "note": "How closely the résumé's wording and experience match the job description (semantic similarity). Not itemised."},
            {"key": "tier3", "label": "AI evaluation", "score": cand.tier3 or 0.0, "max": float(cfg.get("llm_weight", 30)),
             "weight": weight(3), "note": t3_note, "fallback": bool(t3_data.get("is_fallback")), "skipped": ungraded},
        ],
        "warnings": [str(w) for w in warnings],
    }
