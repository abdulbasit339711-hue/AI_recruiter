import asyncio
import json
import logging
import os
import queue as _queue
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from math import ceil
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse, FileResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy import func
from sqlalchemy import text
from sqlalchemy.orm import Session

from .core.logging_config import setup_logging
from .core import status as S
from .core.auth import admin_token_guard, token_is_valid
from .core.ratelimit import upload_rate_limit, jobs_rate_limit, iq_rate_limit
from .core.jd_embedding_cache import invalidate_job, cache_stats
from .core.model_registry import models_loaded
from .database import engine, Base, get_db, config, run_migrations, DATABASE_URL
from .models import Candidate, Job
from .intake.upload import validate_and_extract, IngestionError
from .schemas import (
    StatusUpdateRequest,
    NoteRequest,
    ScoreOverrideRequest,
    CandidateResponse,
    TimelineEntry,
    TimelineResponse,
    IqTestResponse,
    IqSubmitRequest,
    IqSubmitResponse,
)
from .iq import (
    sample_questions,
    score_answers,
    mint_test_token,
    verify_test_token,
    mint_result_token,
    verify_result_token,
    IqTokenError,
)
from .queue.worker import enqueue_candidate, start_worker, stop_worker, get_queue_stats
from .services.email import OutgoingEmail, get_email_sender
from .llm.groq_client import groq_circuit_state, get_groq_client
from .events.broadcaster import event_hub
from .events.sse import stream_candidate_events, stream_job_events
from .events import publish_candidate_event

load_dotenv()
setup_logging(config.get("logging", {}).get("level", "INFO"))
logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Naive UTC timestamp — drop-in for the deprecated stdlib utcnow().

    Keeps the existing naive-UTC `.isoformat()`/`.strftime()` output byte-for-byte
    so stored timestamps don't change format."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    event_hub.bind_loop(asyncio.get_running_loop())
    Base.metadata.create_all(bind=engine)
    run_migrations()
    start_worker()
    get_groq_client()
    # Load heavy sentence‑transformer embedding model once at startup to avoid first‑request latency
    from .core.model_registry import get_embedding_model
    get_embedding_model()
    yield
    # Shutdown
    stop_worker()


app = FastAPI(title="AI Recruiter API", version="2.0.0", lifespan=lifespan)

# Require a valid admin bearer token on every non-public endpoint (logic in
# core/auth.py so it stays unit-testable).
app.middleware("http")(admin_token_guard)

# Added AFTER the auth guard so CORS stays the OUTERMOST middleware — this ensures
# even 401/503 responses carry CORS headers. Explicit allowlist instead of "*".
_cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/")
def read_root():
    return {"message": "AI Recruiter API is running.", "version": "2.0.0"}


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Operational health for load balancers and monitoring."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    loaded = models_loaded()
    stats = get_queue_stats()
    jd_cache = cache_stats()

    overall = "healthy" if db_ok else "degraded"
    return {
        "status": overall,
        "database": "connected" if db_ok else "disconnected",
        "database_url_type": "postgresql" if DATABASE_URL.startswith("postgresql") else "sqlite",
        "model_loaded": loaded.get("embeddings", False),
        "spacy_loaded": loaded.get("spacy", False),
        "queue_depth": stats.depth,
        "queue_processing": stats.processing,
        "groq_status": groq_circuit_state(),
        "jd_embedding_cache": jd_cache,
    }


@app.get("/metrics")
def get_metrics(db: Session = Depends(get_db)):
    total_jobs = db.query(Job).count()
    total_candidates = db.query(Candidate).count()
    avg_score = db.query(func.avg(Candidate.total_score)).scalar() or 0.0
    queued = db.query(Candidate).filter(Candidate.status.in_([S.QUEUED, S.PROCESSING, "Pending"])).count()
    processed = (
        db.query(Candidate)
        .filter(Candidate.status.in_([S.SHORTLISTED, S.REVIEWED, S.REJECTED, S.UNGRADED, "Processed"]))
        .count()
    )
    failed = db.query(Candidate).filter(Candidate.status.in_([S.ERROR, "Failed"])).count()
    return {
        "totalJobs": total_jobs,
        "totalCandidates": total_candidates,
        "avgScore": float(avg_score),
        "pendingCount": queued,
        "processedCount": processed,
        "failedCount": failed,
    }


# ==========================================
# JOBS CRUD
# ==========================================

@app.post("/jobs")
def create_job(
    title: str,
    department: str,
    job_description: str,
    llm_prompt: Optional[str] = None,
    db: Session = Depends(get_db),
):
    try:
        job = Job(
            title=title,
            department=department,
            job_description=job_description,
            llm_prompt=llm_prompt,
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
    }
    if include_private:
        data["llm_prompt"] = job.llm_prompt
        data["tier1_weight"] = job.tier1_weight if job.tier1_weight is not None else 1.0
        data["tier2_weight"] = job.tier2_weight if job.tier2_weight is not None else 1.0
        data["tier3_weight"] = job.tier3_weight if job.tier3_weight is not None else 1.0
    return data


@app.get("/jobs", dependencies=[Depends(jobs_rate_limit)])
def list_jobs(request: Request, status: Optional[str] = "Active", db: Session = Depends(get_db)):
    is_admin = token_is_valid(request.headers.get("authorization"))
    # Unauthenticated callers (the public careers page) only ever see Active postings.
    query = db.query(Job)
    if is_admin:
        if status:
            query = query.filter(Job.status == status)
    else:
        query = query.filter(Job.status == "Active")
    return [_serialize_job(j, is_admin) for j in query.all()]


@app.get("/jobs/{job_id}")
def get_job(job_id: int, request: Request, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    is_admin = token_is_valid(request.headers.get("authorization"))
    return _serialize_job(job, is_admin)


@app.get("/jobs/{job_id}/scoring-weights")
def get_scoring_weights(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "tier1_weight": job.tier1_weight if job.tier1_weight is not None else 1.0,
        "tier2_weight": job.tier2_weight if job.tier2_weight is not None else 1.0,
        "tier3_weight": job.tier3_weight if job.tier3_weight is not None else 1.0,
    }


@app.put("/jobs/{job_id}/scoring-weights")
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


@app.put("/jobs/{job_id}")
def update_job(
    job_id: int,
    title: Optional[str] = None,
    department: Optional[str] = None,
    job_description: Optional[str] = None,
    llm_prompt: Optional[str] = None,
    status: Optional[str] = None,
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
        db.commit()
        db.refresh(job)
        return job
    except Exception:
        db.rollback()
        logger.exception("Database update failed")
        raise HTTPException(status_code=500, detail="Database update failed.")


@app.patch("/jobs/{job_id}")
def patch_job(
    job_id: int,
    department: Optional[str] = None,
    job_description: Optional[str] = None,
    llm_prompt: Optional[str] = None,
    status: Optional[str] = None,
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


@app.delete("/jobs/{job_id}")
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


# ==========================================
# UPLOAD (immediate response + background queue)
# ==========================================

# ==========================================
# IQ SCREEN (public, pre-application)
# ==========================================

@app.get("/iq-test", response_model=IqTestResponse, dependencies=[Depends(iq_rate_limit)])
def get_iq_test(job_id: int = Query(..., description="Target Job ID"), db: Session = Depends(get_db)):
    """Serve a sampled, time-limited IQ test for the apply flow.

    Returns questions WITHOUT correct answers plus a signed token pinning which
    questions were served and a server-enforced deadline. Public, like /upload.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    if job.status == "Archived":
        raise HTTPException(status_code=400, detail=f"Job '{job.title}' is archived.")

    iq_cfg = config.get("iq", {}) or {}
    n = int(iq_cfg.get("num_questions", 10))
    ttl = int(iq_cfg.get("time_limit_seconds", 600))
    questions = sample_questions(n)
    token = mint_test_token(job_id, [q.id for q in questions], ttl_seconds=ttl)
    return {
        "questions": [q.to_public() for q in questions],
        "test_token": token,
        "time_limit_seconds": ttl,
        "total": len(questions),
    }


@app.post("/iq-test/submit", response_model=IqSubmitResponse, dependencies=[Depends(iq_rate_limit)])
def submit_iq_test(payload: IqSubmitRequest):
    """Score answers server-side against the bank and issue a signed result token.

    The result token is what the applicant later hands to /upload so the score is
    attached to their candidate row (tamper-proof, so it can ride through the client).
    """
    try:
        claims = verify_test_token(payload.test_token)
    except IqTokenError as e:
        raise HTTPException(status_code=400, detail=f"Invalid or expired test: {e}")

    correct, total = score_answers(payload.answers, claims.question_ids)
    score = round((correct / total) * 100, 2) if total else 0.0
    result_ttl = int((config.get("iq", {}) or {}).get("result_ttl_seconds", 3600))
    result_token = mint_result_token(claims.job_id, correct, total, score, ttl_seconds=result_ttl)
    return {"correct": correct, "total": total, "score": score, "result_token": result_token}


@app.post("/upload", dependencies=[Depends(upload_rate_limit)])
async def upload_resume(
    job_id: int = Query(..., description="Target Job ID"),
    file: UploadFile = File(...),
    iq_token: Optional[str] = Form(None, description="Signed IQ result token (optional)"),
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
        )
        # Attach the IQ screen result if a valid token was supplied. This NEVER
        # blocks the application: an absent/invalid/mismatched token simply leaves
        # the IQ score null.
        if iq_token:
            try:
                res = verify_result_token(iq_token)
                if res.job_id == job_id:
                    candidate.iq_score = res.score
                    candidate.iq_correct = res.correct
                    candidate.iq_total = res.total
                else:
                    logger.warning(
                        "IQ token job mismatch (token job=%s, upload job=%s); ignoring.",
                        res.job_id, job_id,
                    )
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


# ==========================================
# CANDIDATES (paginated)
# ==========================================

@app.get("/jobs/{job_id}/candidates")
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


@app.get("/candidates/{candidate_id}")
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return candidate


@app.get("/candidates/{candidate_id}/resume", response_class=PlainTextResponse)
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


@app.patch("/candidates/{candidate_id}/status", response_model=CandidateResponse)
def update_candidate_status(
    candidate_id: int,
    payload: StatusUpdateRequest,
    db: Session = Depends(get_db),
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
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


@app.post("/candidates/{candidate_id}/notes", response_model=CandidateResponse)
def add_candidate_note(
    candidate_id: int,
    payload: NoteRequest,
    db: Session = Depends(get_db),
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
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


@app.patch("/candidates/{candidate_id}/score-override", response_model=CandidateResponse)
def override_candidate_score(
    candidate_id: int,
    payload: ScoreOverrideRequest,
    db: Session = Depends(get_db),
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
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


@app.get("/candidates/{candidate_id}/timeline", response_model=TimelineResponse)
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


@app.get("/candidates/{candidate_id}/events")
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


@app.get("/jobs/{job_id}/events")
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


@app.post("/candidates/{candidate_id}/reprocess")
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


@app.post("/candidates/{candidate_id}/resume", dependencies=[Depends(upload_rate_limit)])
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


@app.post("/jobs/{job_id}/reprocess")
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


@app.get("/candidates/{candidate_id}/interview")
def get_candidate_interview(candidate_id: int, db: Session = Depends(get_db)):
    """Return the candidate's AI interview results (transcript + goals + assessment).

    Reads the voice agent's tables, which live in the same PostgreSQL database.
    """
    from sqlalchemy import text

    # Per-candidate resume-scoring (Tier 3) token usage + cost, captured at scoring time.
    cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    scoring_metrics = {
        "prompt_tokens": (cand.llm_prompt_tokens or 0) if cand else 0,
        "completion_tokens": (cand.llm_completion_tokens or 0) if cand else 0,
        "cost_usd": round(float(cand.llm_cost_usd or 0.0), 6) if cand else 0.0,
    }

    sess = db.execute(text(
        "SELECT session_id, role_type, status, started_at, ended_at, total_goals, "
        "completed_goals, average_progress, overall_assessment, audio_path "
        "FROM interview_sessions WHERE candidate_id = :cid "
        "ORDER BY created_at DESC LIMIT 1"
    ), {"cid": candidate_id}).mappings().first()
    if not sess:
        return {
            "has_interview": False,
            "metrics": {
                "interview": {
                    "stt_tokens": 0, "llm_input_tokens": 0, "llm_output_tokens": 0,
                    "tts_tokens": 0, "total_tokens": 0, "cost_usd": 0.0,
                },
                "scoring": scoring_metrics,
            },
        }

    sid = sess["session_id"]
    transcript = db.execute(text(
        "SELECT speaker, text, sequence_number, evaluation FROM session_transcripts "
        "WHERE session_id = :sid ORDER BY sequence_number"
    ), {"sid": sid}).mappings().all()
    # Include each goal's planned questions (goal_templates.question_templates) and the
    # candidate-answer evidence gathered for it (session_goals.evidence), so HR can see
    # the goal-related questions and the candidate's answers alongside the goal score.
    goals = db.execute(text(
        "SELECT gt.title, sg.completion_status, sg.progress_score, sg.confidence_level, "
        "gt.question_templates, sg.evidence "
        "FROM session_goals sg JOIN goal_templates gt ON sg.goal_template_id = gt.id "
        "WHERE sg.session_id = :sid ORDER BY gt.priority_weight DESC"
    ), {"sid": sid}).mappings().all()

    # Aggregate the interview token usage by service/type (LLM in/out, TTS) from
    # session_metrics; cost is only the real LLM cost (goal_analysis rows carry a
    # placeholder cost and are excluded).
    by_type = db.execute(text(
        "SELECT metric_type, COALESCE(SUM(token_count), 0) AS tokens, "
        "COALESCE(SUM(cost_usd), 0) AS cost "
        "FROM session_metrics WHERE session_id = :sid GROUP BY metric_type"
    ), {"sid": sid}).mappings().all()
    tok = {r["metric_type"]: int(r["tokens"]) for r in by_type}
    cost_by = {r["metric_type"]: float(r["cost"]) for r in by_type}
    interview_cost = round(cost_by.get("llm_input", 0.0) + cost_by.get("llm_output", 0.0), 6)
    # STT tokens come from the candidate transcript word counts (the metrics processor
    # sits after the user-aggregator and never sees the raw transcription frames).
    stt_t = int(db.execute(text(
        "SELECT COALESCE(SUM(tokens_estimated), 0) FROM session_transcripts "
        "WHERE session_id = :sid AND speaker = 'candidate'"
    ), {"sid": sid}).scalar() or 0)
    llm_in = tok.get("llm_input", 0)
    llm_out = tok.get("llm_output", 0)
    tts_t = tok.get("tts_tokens", 0)
    interview_metrics = {
        "stt_tokens": stt_t,
        "llm_input_tokens": llm_in,
        "llm_output_tokens": llm_out,
        "tts_tokens": tts_t,
        "total_tokens": stt_t + llm_in + llm_out + tts_t,
        "cost_usd": interview_cost,
    }

    session_dict = dict(sess)
    has_audio = bool(session_dict.pop("audio_path", None))

    def _norm_goal(g) -> dict:
        """Flatten a goal row into {title, status, scores, questions[], evidence[{text}]}.
        question_templates / evidence are jsonb whose items may be plain strings or dicts."""
        d = dict(g)
        qt = d.pop("question_templates", None) or []
        d["questions"] = [
            (q if isinstance(q, str) else (q.get("text") or q.get("question") or "")).strip()
            for q in (qt if isinstance(qt, list) else [])
        ]
        d["questions"] = [q for q in d["questions"] if q]
        ev = d.get("evidence") or []
        d["evidence"] = [
            {"text": (e if isinstance(e, str)
                      else (e.get("text") or e.get("quote") or e.get("evidence_text") or "")).strip()}
            for e in (ev if isinstance(ev, list) else [])
        ]
        d["evidence"] = [e for e in d["evidence"] if e["text"]]
        return d

    return {
        "has_interview": True,
        "has_audio": has_audio,
        "session": session_dict,
        "transcript": [dict(t) for t in transcript],
        "goals": [_norm_goal(g) for g in goals],
        "metrics": {
            "interview": interview_metrics,
            "scoring": scoring_metrics,
        },
    }


@app.get("/candidates/{candidate_id}/interview-audio")
def get_candidate_interview_audio(candidate_id: int, db: Session = Depends(get_db)):
    """Stream the recorded interview audio (merged WAV) for HR playback.

    The voice agent writes recordings to RECORDINGS_DIR and stores the path on the
    interview_sessions row; this serves that file back through the admin proxy.
    """
    from sqlalchemy import text

    audio_path = db.execute(text(
        "SELECT audio_path FROM interview_sessions WHERE candidate_id = :cid "
        "ORDER BY created_at DESC LIMIT 1"
    ), {"cid": candidate_id}).scalar()

    if not audio_path or not os.path.isfile(audio_path):
        raise HTTPException(status_code=404, detail="Interview audio not found.")

    return FileResponse(audio_path, media_type="audio/wav", filename=os.path.basename(audio_path))


def _build_candidate_report_md(candidate: Candidate, job_title: str, interview: dict) -> str:
    """Assemble a single Markdown report: résumé tier scores + AI-interview assessment +
    transcript. Reuses the candidate record and the get_candidate_interview payload."""
    def _parse(x):
        if isinstance(x, (dict, list)):
            return x
        try:
            return json.loads(x) if x else None
        except (TypeError, ValueError):
            return None

    name = candidate.name or candidate.filename or f"Candidate {candidate.id}"
    L = [
        f"# Candidate Report — {name}",
        "",
        f"- **Job:** {job_title}",
        f"- **Email:** {candidate.email or 'n/a'}",
        f"- **Status:** {candidate.status}",
        "",
        "## Résumé score",
        f"- Tier 1 (profile rules): {candidate.tier1}/30",
        f"- Tier 2 (semantic match): {candidate.tier2}/40",
        f"- Tier 3 (LLM evaluation): {candidate.tier3}/30",
        f"- **Total: {candidate.total_score}/100**",
    ]
    if candidate.summary:
        L += ["", "### Summary", candidate.summary]
    ev = _parse(candidate.evidence)
    if ev:
        L += ["", "### Evidence"]
        L += [f"- {e if isinstance(e, str) else json.dumps(e)}" for e in (ev if isinstance(ev, list) else [ev])]

    L += ["", "## AI interview"]
    if not interview.get("has_interview"):
        L.append("_No interview conducted yet._")
    else:
        sess = interview.get("session") or {}
        L += [f"- Role: {sess.get('role_type')}", f"- Status: {sess.get('status')}"]
        oa = _parse(sess.get("overall_assessment"))
        ov = (oa or {}).get("overall_assessment") if isinstance(oa, dict) else None
        if isinstance(ov, dict):
            if ov.get("hiring_recommendation"):
                L.append(f"- **Recommendation: {ov['hiring_recommendation']}**")
            for label, key in (("Strengths", "strengths"), ("Areas for improvement", "areas_for_improvement")):
                vals = ov.get(key) or []
                if vals:
                    L.append(f"- {label}: " + "; ".join(str(v) for v in vals))
        L.append(f"- Recording: {'available' if interview.get('has_audio') else 'none'}")
        transcript = interview.get("transcript") or []
        if transcript:
            L += ["", "### Transcript"]
            for t in transcript:
                who = "Interviewer" if t.get("speaker") == "agent" else "Candidate"
                L.append(f"- **{who}:** {t.get('text')}")
    return "\n".join(L)


def _markdown_to_pdf_bytes(md: str, title: str) -> bytes:
    """Render the report Markdown to a simple PDF via reportlab (headings + bullets)."""
    import io, re, html
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, title=title)
    styles = getSampleStyleSheet()
    flow = []
    for raw in md.split("\n"):
        line = raw.rstrip()
        if not line:
            flow.append(Spacer(1, 6))
            continue
        if line.startswith("### "):
            style, line = styles["Heading3"], line[4:]
        elif line.startswith("## "):
            style, line = styles["Heading2"], line[3:]
        elif line.startswith("# "):
            style, line = styles["Title"], line[2:]
        else:
            style = styles["BodyText"]
        text = html.escape(line.lstrip("- ") if line.startswith("- ") else line)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        if raw.startswith("- "):
            text = "• " + text
        flow.append(Paragraph(text, style))
    doc.build(flow)
    return buf.getvalue()


@app.get("/candidates/{candidate_id}/report")
def candidate_report(candidate_id: int, format: str = Query("md", pattern="^(md|pdf)$"),
                     db: Session = Depends(get_db)):
    """One-click report combining the résumé score and the AI-interview assessment."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    job = db.query(Job).filter(Job.id == candidate.job_id).first()
    interview = get_candidate_interview(candidate_id, db)  # reuse the existing assembler
    md = _build_candidate_report_md(candidate, job.title if job else "n/a", interview)
    stem = f"candidate_{candidate_id}_report"
    if format == "pdf":
        try:
            pdf = _markdown_to_pdf_bytes(md, title=stem)
        except ImportError:
            raise HTTPException(status_code=501, detail="PDF export requires reportlab (pip install reportlab).")
        import io
        return StreamingResponse(
            io.BytesIO(pdf), media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{stem}.pdf"'},
        )
    return PlainTextResponse(
        md, headers={"Content-Disposition": f'attachment; filename="{stem}.md"'}
    )


@app.post("/candidates/{candidate_id}/interview-invite")
def send_interview_invite_api(candidate_id: int, db: Session = Depends(get_db)):
    """HR action: (re)send the time-limited AI-interview link to a candidate."""
    cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if not cand.email:
        raise HTTPException(status_code=400, detail="Candidate has no email address.")
    job = db.query(Job).filter(Job.id == cand.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Candidate is not linked to a job.")
    from .services.interview_invite import invite_candidate
    url = invite_candidate(db, cand, job, force=True)
    return {"status": "sent", "candidate_id": candidate_id, "link": url}


@app.post("/jobs/{job_id}/email")
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
