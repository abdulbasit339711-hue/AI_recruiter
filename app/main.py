import asyncio
import json
import logging
import os
import queue as _queue
import time as _time
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
from .database import engine, Base, get_db, config, run_migrations, DATABASE_URL, get_setting
from .models import Candidate, Job, Org, Setting
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
    AvailabilitySubmit,
    SlotConfirm,
)
from .iq import (
    sample_questions,
    score_answers,
    time_adjusted_score,
    build_detail,
    mint_test_token,
    verify_test_token,
    mint_result_token,
    verify_result_token,
    IqTokenError,
)
from .queue.worker import enqueue_candidate, start_worker, stop_worker, get_queue_stats, requeue_pending
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
    requeue_pending()  # recover candidates a prior crash left in Queued/Processing
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
def get_metrics(
    job_id: Optional[int] = Query(None),
    from_date: Optional[str] = Query(None, description="ISO date string YYYY-MM-DD (inclusive)"),
    to_date: Optional[str] = Query(None, description="ISO date string YYYY-MM-DD (inclusive)"),
    db: Session = Depends(get_db),
):
    def _q(model):
        q = db.query(model)
        if model is Candidate:
            if job_id is not None:
                q = q.filter(Candidate.job_id == job_id)
            if from_date:
                q = q.filter(Candidate.created_at >= from_date)
            if to_date:
                # Include the full to_date day by comparing against the day after
                q = q.filter(Candidate.created_at <= to_date + "T23:59:59")
        return q

    total_jobs = 1 if job_id is not None else db.query(Job).count()
    total_candidates = _q(Candidate).count()
    avg_score = _q(Candidate).with_entities(func.avg(Candidate.total_score)).scalar() or 0.0
    queued = _q(Candidate).filter(Candidate.status.in_([S.QUEUED, S.PROCESSING, "Pending"])).count()
    processed = (
        _q(Candidate)
        .filter(Candidate.status.in_([S.SHORTLISTED, S.REVIEWED, S.REJECTED, S.UNGRADED, "Processed"]))
        .count()
    )
    failed = _q(Candidate).filter(Candidate.status.in_([S.ERROR, "Failed"])).count()
    buckets = [("0–20", 0, 20), ("21–40", 21, 40), ("41–60", 41, 60), ("61–80", 61, 80), ("81–100", 81, 100)]
    score_distribution = []
    for label, lo, hi in buckets:
        count = (
            _q(Candidate)
            .filter(Candidate.total_score >= lo, Candidate.total_score <= hi)
            .count()
        )
        score_distribution.append({"label": label, "count": count})

    shortlisted_count = _q(Candidate).filter(
        Candidate.status.in_([S.SHORTLISTED, "Shortlisted"])
    ).count()
    top_score = float(_q(Candidate).with_entities(func.max(Candidate.total_score)).scalar() or 0.0)

    return {
        "totalJobs": total_jobs,
        "totalCandidates": total_candidates,
        "avgScore": float(avg_score),
        "pendingCount": queued,
        "processedCount": processed,
        "failedCount": failed,
        "scoreDistribution": score_distribution,
        "shortlistedCount": shortlisted_count,
        "topScore": top_score,
    }


# ==========================================
# ORGS CRUD
# ==========================================

@app.post("/orgs")
def create_org(
    slug: str = Query(..., min_length=1, max_length=80),
    name: str = Query(..., min_length=1, max_length=200),
    primary_color: Optional[str] = Query("#1C99BF", max_length=20),
    logo_url: Optional[str] = Query(None, max_length=500),
    tagline: Optional[str] = Query(None, max_length=300),
    about: Optional[str] = Query(None, max_length=5000),
    contact_email: Optional[str] = Query(None, max_length=200),
    social_links: Optional[str] = Query(None, max_length=1000),
    db: Session = Depends(get_db),
):
    import json as _json, re as _re
    if not _re.match(r'^[a-z0-9-]+$', slug):
        raise HTTPException(status_code=422, detail="Slug must be lowercase letters, digits, and hyphens only.")
    if db.query(Org).filter(Org.slug == slug).first():
        raise HTTPException(status_code=409, detail="An org with this slug already exists.")
    try:
        _json.loads(social_links) if social_links else {}
    except Exception:
        raise HTTPException(status_code=422, detail="social_links must be valid JSON.")
    org = Org(
        slug=slug,
        name=name,
        primary_color=primary_color or "#1C99BF",
        logo_url=logo_url,
        tagline=tagline,
        about=about,
        contact_email=contact_email,
        social_links=social_links,
        created_at=_utcnow().isoformat(),
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return _serialize_org(org)


@app.get("/orgs")
def list_orgs(db: Session = Depends(get_db)):
    return [_serialize_org(o) for o in db.query(Org).order_by(Org.name).all()]


@app.get("/orgs/{slug}")
def get_org(slug: str, db: Session = Depends(get_db)):
    org = db.query(Org).filter(Org.slug == slug).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return _serialize_org(org)


@app.get("/orgs/{slug}/jobs")
def get_org_jobs(slug: str, db: Session = Depends(get_db)):
    org = db.query(Org).filter(Org.slug == slug).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")
    jobs = db.query(Job).filter(Job.org_id == org.id, Job.status == "Active").all()
    if jobs:
        job_ids = [j.id for j in jobs]
        counts = dict(
            db.query(Candidate.job_id, func.count(Candidate.id))
            .filter(Candidate.job_id.in_(job_ids))
            .group_by(Candidate.job_id)
            .all()
        )
    else:
        counts = {}
    return [dict(**_serialize_job(j, False), candidate_count=counts.get(j.id, 0)) for j in jobs]


@app.patch("/orgs/{org_id}")
def update_org(
    org_id: int,
    name: Optional[str] = Query(None, max_length=200),
    primary_color: Optional[str] = Query(None, max_length=20),
    logo_url: Optional[str] = Query(None, max_length=500),
    tagline: Optional[str] = Query(None, max_length=300),
    about: Optional[str] = Query(None, max_length=5000),
    contact_email: Optional[str] = Query(None, max_length=200),
    social_links: Optional[str] = Query(None, max_length=1000),
    db: Session = Depends(get_db),
):
    import json as _json
    org = db.query(Org).filter(Org.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")
    if name is not None:
        org.name = name
    if primary_color is not None:
        org.primary_color = primary_color
    if logo_url is not None:
        org.logo_url = logo_url or None
    if tagline is not None:
        org.tagline = tagline or None
    if about is not None:
        org.about = about or None
    if contact_email is not None:
        org.contact_email = contact_email or None
    if social_links is not None:
        try:
            _json.loads(social_links) if social_links else {}
        except Exception:
            raise HTTPException(status_code=422, detail="social_links must be valid JSON.")
        org.social_links = social_links or None
    db.commit()
    db.refresh(org)
    return _serialize_org(org)


@app.delete("/orgs/{org_id}")
def delete_org(org_id: int, db: Session = Depends(get_db)):
    org = db.query(Org).filter(Org.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")
    # Detach jobs before deletion so they're not orphaned
    db.query(Job).filter(Job.org_id == org_id).update({"org_id": None})
    db.delete(org)
    db.commit()
    return {"message": "Organization deleted.", "org_id": org_id}


# ==========================================
# ADMIN SETTINGS
# ==========================================

_SETTING_DEFS: dict[str, dict] = {
    "availability_threshold": {
        "label": "Availability Invite Threshold",
        "description": "Minimum total score (0–100) a candidate must reach before the system auto-sends them the interview availability form.",
        "type": "number",
        "min": 0,
        "max": 100,
    },
}


@app.get("/settings")
def list_settings(db: Session = Depends(get_db)):
    rows = db.query(Setting).all()
    by_key = {r.key: r.value for r in rows}
    return [
        {
            "key": key,
            "value": by_key.get(key),
            "description": meta["description"],
            "label": meta["label"],
            "type": meta.get("type", "string"),
            "min": meta.get("min"),
            "max": meta.get("max"),
        }
        for key, meta in _SETTING_DEFS.items()
    ]


@app.patch("/settings/{key}")
def update_setting(key: str, value: str = Query(...), db: Session = Depends(get_db)):
    if key not in _SETTING_DEFS:
        raise HTTPException(status_code=404, detail=f"Unknown setting: {key}")
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = value
    else:
        row = Setting(key=key, value=value, description=_SETTING_DEFS[key]["description"])
        db.add(row)
    db.commit()
    return {"key": key, "value": value}


# ==========================================
# JOBS CRUD
# ==========================================

@app.post("/jobs")
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
    jobs_list = query.all()
    # Batch-count candidates per job in a single query (avoids N+1).
    if jobs_list:
        job_ids = [j.id for j in jobs_list]
        counts = dict(
            db.query(Candidate.job_id, func.count(Candidate.id))
            .filter(Candidate.job_id.in_(job_ids))
            .group_by(Candidate.job_id)
            .all()
        )
    else:
        counts = {}
    return [dict(**_serialize_job(j, is_admin), candidate_count=counts.get(j.id, 0)) for j in jobs_list]


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


@app.patch("/jobs/{job_id}")
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

    iq_cfg = config.get("iq", {}) or {}
    time_limit = int(iq_cfg.get("time_limit_seconds", 600))
    speed_weight = float(iq_cfg.get("speed_weight", 0.2))
    # Time taken is measured server-side (test issuance -> submit), so it can't be
    # forged by the client; clamped to the time limit.
    elapsed = min(max(0, int(_time.time()) - claims.iat), time_limit)

    correct, total = score_answers(payload.answers, claims.question_ids)
    accuracy = round((correct / total) * 100, 2) if total else 0.0
    score = time_adjusted_score(correct, total, elapsed, time_limit, speed_weight)
    detail = build_detail(claims.question_ids, payload.answers, payload.times or {})

    result_ttl = int(iq_cfg.get("result_ttl_seconds", 3600))
    result_token = mint_result_token(
        claims.job_id, correct, total, score,
        time_seconds=elapsed, detail=detail, ttl_seconds=result_ttl,
    )
    return {
        "correct": correct,
        "total": total,
        "accuracy": accuracy,
        "score": score,
        "time_seconds": elapsed,
        "detail": detail,
        "result_token": result_token,
    }


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
                if res.job_id != job_id:
                    logger.warning(
                        "IQ token job mismatch (token job=%s, upload job=%s); ignoring.",
                        res.job_id, job_id,
                    )
                elif res.jti and db.query(Candidate.id).filter(
                    Candidate.iq_result_jti == res.jti
                ).first():
                    # Single-use: this signed result was already attached to a prior
                    # upload. Don't let one score be replayed across many candidates.
                    logger.warning("IQ token replay (jti=%s already used); ignoring.", res.jti)
                else:
                    candidate.iq_score = res.score
                    candidate.iq_correct = res.correct
                    candidate.iq_total = res.total
                    candidate.iq_time_seconds = res.time_seconds
                    candidate.iq_details = json.dumps(res.detail) if res.detail else None
                    candidate.iq_result_jti = res.jti or None
                    # When the screen was taken (result token issuance = submit time).
                    candidate.iq_attempted_at = datetime.fromtimestamp(
                        res.iat, tz=timezone.utc
                    ).isoformat()
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


@app.post("/candidates/{candidate_id}/notes", response_model=CandidateResponse)
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


@app.patch("/candidates/{candidate_id}/score-override", response_model=CandidateResponse)
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


def _recordings_dir() -> str:
    return os.getenv("RECORDINGS_DIR", "/mnt/muaaz/AI_recruiter/data/recordings")


def _session_media(session_id: str) -> dict:
    """Resolve a session's on-disk media by the ``{session_id}.{ext}`` naming
    convention the voice agent uses. We deliberately do NOT rely on the
    interview_sessions.audio_path column — it is frequently empty even when the
    files exist on disk, which previously hid the recording from HR."""
    d = _recordings_dir()
    paths = {
        "audio": os.path.join(d, f"{session_id}.wav"),
        "video": os.path.join(d, f"{session_id}.mp4"),
        "annotated": os.path.join(d, f"{session_id}.annotated.mp4"),
        "vision": os.path.join(d, f"{session_id}.vision.json"),
        "comm": os.path.join(d, f"{session_id}.comm.json"),
    }
    return {k: (v if os.path.isfile(v) else None) for k, v in paths.items()}


def _vision_overall_summary(aggregate: dict, observations: list) -> str:
    """Synthesize a video-LEVEL narrative from the per-frame observations.

    The VLM emits one caption per sampled frame ("a person at a desk…"); on their
    own those are just image descriptions. This rolls them up into a few sentences
    describing the candidate's on-camera presentation across the whole interview."""
    agg = aggregate or {}
    obs = observations or []
    n = agg.get("frames_analyzed") or len(obs)
    if not n:
        return ""
    parts: list[str] = []

    present = agg.get("present_ratio")
    if present is not None:
        pct = round(present * 100)
        if pct >= 90:
            parts.append("The candidate was on camera for essentially the entire interview")
        elif pct >= 60:
            parts.append(f"The candidate was visible for about {pct}% of the interview")
        else:
            parts.append(f"The candidate was visible for only about {pct}% of the interview (frequently off-camera)")

    eng = agg.get("avg_engagement")
    if eng is not None:
        # engagement is reported 0–5 by the VLM
        if eng >= 3.5:
            desc = "high, sustained attentiveness"
        elif eng >= 2:
            desc = "moderate attentiveness"
        else:
            desc = "low or inconsistent attentiveness"
        parts.append(f"showing {desc} (avg {eng}/5)")

    looking_away = sum(1 for o in obs if o.get("looking_away"))
    if obs and looking_away:
        parts.append(f"appeared to look off-screen in {looking_away} of {len(obs)} sampled moments")

    # Distinct delivery notes, de-duplicated, as a flavour of how they presented.
    notes = []
    seen = set()
    for o in obs:
        dn = (o.get("delivery_notes") or "").strip().rstrip(".")
        key = dn.lower()
        if dn and key not in seen:
            seen.add(key)
            notes.append(dn)
    summary = ". ".join(p for p in [", ".join(parts[:1] + parts[1:])] if p)
    if summary:
        summary += "."
    if notes:
        summary += " Delivery cues observed: " + "; ".join(notes[:5]) + "."

    flags = agg.get("integrity_flags") or []
    if flags:
        labels = {"candidate_absent": "candidate absent at times",
                  "phone_visible": "a phone was visible", "multiple_people": "more than one person seen"}
        summary += " Integrity notes: " + ", ".join(labels.get(f, f) for f in flags) + "."
    return summary.strip()


def _vision_data_quality(aggregate: dict) -> dict:
    """Gate the subjective video read on how much usable footage we actually had.
    Prevents a confident-sounding summary built on 2 frames of an off-camera candidate."""
    agg = aggregate or {}
    frames = agg.get("frames_analyzed") or 0
    present = agg.get("present_ratio")
    present = present if present is not None else 0.0
    if frames < 2 or present < 0.25:
        level, note = "insufficient", "Too little on-camera footage to assess delivery reliably."
    elif frames < 4 or present < 0.6:
        level, note = "limited", "Limited on-camera footage — read delivery cues with caution."
    else:
        level, note = "good", "Sufficient on-camera footage for an advisory read."
    return {"level": level, "note": note, "frames_analyzed": frames,
            "present_ratio": round(present, 2)}


def _speaking_metrics(transcript, session: dict) -> dict:
    """Objective communication signals from the transcript + session duration:
    talk-time balance (candidate vs interviewer) and an approximate speaking pace."""
    import re as _re

    def _words(s: str) -> int:
        return len(_re.findall(r"[A-Za-z0-9']+", s or ""))

    cand_turns = [t for t in transcript if t.get("speaker") == "candidate"]
    agent_turns = [t for t in transcript if t.get("speaker") == "agent"]
    cand_words = sum(_words(t.get("text", "")) for t in cand_turns)
    agent_words = sum(_words(t.get("text", "")) for t in agent_turns)
    total = cand_words + agent_words

    duration_s = None
    started, ended = session.get("started_at"), session.get("ended_at")
    if started and ended:
        try:
            duration_s = max(0.0, (ended - started).total_seconds())
        except Exception:
            duration_s = None

    # Approximate pace over the whole interview (not just speaking time), clearly labelled.
    wpm = round(cand_words / (duration_s / 60), 1) if duration_s and duration_s > 0 else None
    return {
        "candidate_words": cand_words,
        "interviewer_words": agent_words,
        "candidate_talk_ratio_pct": round(100 * cand_words / total, 1) if total else 0.0,
        "candidate_turns": len(cand_turns),
        "interviewer_turns": len(agent_turns),
        "avg_words_per_answer": round(cand_words / len(cand_turns), 1) if cand_turns else 0.0,
        "duration_seconds": round(duration_s) if duration_s is not None else None,
        "approx_words_per_min": wpm,
    }


def _latest_session_id(db: Session, candidate_id: int):
    from sqlalchemy import text
    return db.execute(text(
        "SELECT session_id FROM interview_sessions WHERE candidate_id = :cid "
        "ORDER BY created_at DESC LIMIT 1"
    ), {"cid": candidate_id}).scalar()


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
    db_audio = session_dict.pop("audio_path", None)
    # Resolve media from disk by session_id (audio_path is often empty).
    media = _session_media(sid)
    has_audio = bool(db_audio) or media["audio"] is not None

    # Advisory video-evaluation report (semantic VLM observations + local YOLO
    # proctoring detections), written as a sidecar JSON by the voice agent.
    vision_report = None
    if media["vision"]:
        try:
            import json as _json
            with open(media["vision"]) as _vf:
                _vj = _json.load(_vf)
            _agg = _vj.get("aggregate", {})
            _obs = _vj.get("observations", [])
            _quality = _vision_data_quality(_agg)
            vision_report = {
                "backend": _vj.get("semantic_backend"),
                "advisory_only": _vj.get("advisory_only", True),
                "data_quality": _quality,
                "aggregate": _agg,
                # Suppress the subjective narrative when there isn't enough footage to back it.
                "overall_summary": (_vision_overall_summary(_agg, _obs)
                                    if _quality["level"] != "insufficient" else ""),
                "observations": _obs,
                "detections": _vj.get("detections", []),
            }
        except Exception:
            vision_report = None

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
        "has_video": media["video"] is not None,
        "has_annotated_video": media["annotated"] is not None,
        "has_communication": media["comm"] is not None,
        "vision": vision_report,
        "speaking": _speaking_metrics([dict(t) for t in transcript], session_dict),
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

    # Fall back to the session_id-derived path on disk (audio_path is often empty).
    if not audio_path or not os.path.isfile(audio_path):
        sid = _latest_session_id(db, candidate_id)
        audio_path = _session_media(sid)["audio"] if sid else None

    if not audio_path or not os.path.isfile(audio_path):
        raise HTTPException(status_code=404, detail="Interview audio not found.")

    return FileResponse(audio_path, media_type="audio/wav", filename=os.path.basename(audio_path))


@app.get("/candidates/{candidate_id}/interview-video")
def get_candidate_interview_video(
    candidate_id: int, annotated: bool = False, db: Session = Depends(get_db)
):
    """Stream the recorded interview video for HR playback.

    ``annotated=true`` serves the YOLO-annotated copy (bounding boxes over the
    candidate / detected objects) if it has been generated; otherwise the raw
    muxed MP4. Files are resolved by session_id from RECORDINGS_DIR.
    """
    sid = _latest_session_id(db, candidate_id)
    if not sid:
        raise HTTPException(status_code=404, detail="No interview for this candidate.")
    media = _session_media(sid)
    path = media["annotated"] if annotated else media["video"]
    if not path:
        raise HTTPException(
            status_code=404,
            detail="Annotated video not generated yet." if annotated else "Interview video not found.",
        )
    return FileResponse(path, media_type="video/mp4", filename=os.path.basename(path))


@app.post("/candidates/{candidate_id}/annotate-video")
def annotate_candidate_video(candidate_id: int, db: Session = Depends(get_db)):
    """Kick off offline YOLO annotation of the recorded interview video.

    Runs the annotator under the conda python that has ultralytics/supervision/cv2
    (the voice uv venv does not). Returns immediately; the annotated MP4 appears as
    ``{session_id}.annotated.mp4`` and is then served via interview-video?annotated=true.
    """
    import subprocess

    sid = _latest_session_id(db, candidate_id)
    if not sid:
        raise HTTPException(status_code=404, detail="No interview for this candidate.")
    media = _session_media(sid)
    if not media["video"]:
        raise HTTPException(status_code=404, detail="No interview video to annotate.")
    if media["annotated"]:
        return {"status": "ready", "session_id": sid, "already": True}

    script = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "voice-agent", "server", "scripts", "annotate_video.py",
    )
    py = os.getenv("DETECTOR_PYTHON", "/home/aoi/miniconda3/bin/python")
    if not os.path.isfile(script):
        raise HTTPException(status_code=500, detail="Annotator script missing.")
    try:
        # Detached background job; annotation of a few-minute clip is CPU-heavy.
        subprocess.Popen(
            [py, script, "--session", sid, "--recordings-dir", _recordings_dir()],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start annotator: {e}")
    return {"status": "started", "session_id": sid}


_FILLER_WORDS = ("um", "uh", "uhh", "umm", "hmm", "erm", "er", "ah", "like", "you know")


def _count_fillers(turns) -> dict:
    """Deterministic filler-word tally over the candidate's transcript turns
    (Deepgram filler_words=true surfaces um/uh/hmm in the text)."""
    import re as _re
    total_words = 0
    counts = {f: 0 for f in _FILLER_WORDS}
    for t in turns:
        if t.get("speaker") != "candidate":
            continue
        words = _re.findall(r"[a-zA-Z']+", (t.get("text") or "").lower())
        total_words += len(words)
        for w in words:
            if w in counts:
                counts[w] += 1
    used = {k: v for k, v in counts.items() if v}
    n_fillers = sum(used.values())
    return {
        "total_words": total_words,
        "filler_count": n_fillers,
        "filler_rate_pct": round(100 * n_fillers / total_words, 1) if total_words else 0.0,
        "by_filler": used,
    }


@app.get("/candidates/{candidate_id}/communication-analysis")
def get_communication_analysis(candidate_id: int, refresh: bool = False, db: Session = Depends(get_db)):
    """Detailed delivery/communication assessment over the interview transcript:
    talking style, fluency, pace, clarity, confidence, and a language/phrasing note.

    Cached to a ``{session}.comm.json`` sidecar. NOTE: this is a TEXT analysis — it
    reads the transcript, so it characterises talking style and phrasing, not audio
    accent (true accent classification needs an audio model and is flagged as such).
    """
    from sqlalchemy import text
    import json as _json

    sid = _latest_session_id(db, candidate_id)
    if not sid:
        raise HTTPException(status_code=404, detail="No interview for this candidate.")

    cache = os.path.join(_recordings_dir(), f"{sid}.comm.json")
    if os.path.isfile(cache) and not refresh:
        try:
            with open(cache) as f:
                cached = _json.load(f)
            # Regenerate stale caches written before the content-analysis was added.
            if "content" in cached:
                return cached
        except Exception:
            pass

    turns = db.execute(text(
        "SELECT speaker, text FROM session_transcripts WHERE session_id = :sid "
        "ORDER BY sequence_number"
    ), {"sid": sid}).mappings().all()
    turns = [dict(t) for t in turns]
    cand_turns = [t for t in turns if t.get("speaker") == "candidate"]
    if not cand_turns:
        raise HTTPException(status_code=404, detail="No candidate speech to analyze.")

    fillers = _count_fillers(turns)

    # Build the transcript text for the LLM (candidate turns carry the delivery signal).
    convo = "\n".join(
        f"{'Interviewer' if t['speaker'] == 'agent' else 'Candidate'}: {t['text']}"
        for t in turns
    )[:8000]

    from app.llm.groq_client import get_groq_client, _call_groq_api
    client = get_groq_client()
    analysis = None
    content_eval = None
    if client is not None:
        system_prompt = (
            "You are an interview analyst. From the transcript, produce TWO assessments and "
            "return STRICT minified JSON with exactly two top-level keys: \"delivery\" and \"content\".\n\n"
            "\"delivery\" (HOW the candidate communicates) — object with keys: talking_style, "
            "fluency, pace, clarity, confidence, conciseness, language_phrasing, accent_note. "
            "For accent_note: you only have TEXT, so DO NOT guess a regional/national accent; "
            "comment on vocabulary/idiom/phrasing and state that audio is required for true accent "
            "assessment. Each value is one short sentence.\n\n"
            "\"content\" (WHAT the candidate said — the primary, most job-relevant signal) — object "
            "with keys: star_usage (do answers follow Situation-Task-Action-Result with a concrete, "
            "measurable result? one sentence), specificity (concrete examples vs vague generalities? "
            "one sentence), ownership (does the candidate say what THEY did, 'I' vs 'we' — note this "
            "can be cultural, don't over-penalise; one sentence), relevance (do answers address the "
            "questions asked? one sentence), red_flags (array of short strings: vagueness, evasiveness, "
            "contradictions, rambling, off-topic, negativity — empty array if none), strengths (array "
            "of short strings). Judge job-relevant substance, not accent or personality."
        )
        user_prompt = (
            f"Filler-word stats (from speech-to-text): {fillers['filler_count']} fillers across "
            f"{fillers['total_words']} words ({fillers['filler_rate_pct']}%), breakdown {fillers['by_filler']}.\n\n"
            f"Transcript:\n{convo}\n\nReturn the JSON now."
        )
        try:
            raw, _usage = _call_groq_api(client, "llama-3.3-70b-versatile", system_prompt, user_prompt)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
            parsed = _json.loads(raw)
            analysis = parsed.get("delivery", parsed)   # tolerate flat output
            content_eval = parsed.get("content")
        except Exception as e:
            analysis = {"error": f"LLM analysis unavailable: {e}"}

    result = {
        "session_id": sid,
        "fillers": fillers,
        "analysis": analysis,
        "content": content_eval,
        "candidate_turns": len(cand_turns),
    }
    try:
        with open(cache, "w") as f:
            _json.dump(result, f, indent=2)
    except Exception:
        pass
    return result


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

    # Candidate profile extracted during scoring (role, companies, experience, skills, IQ).
    companies = _parse(candidate.companies) or []
    matched = _parse(candidate.skills_matched) or []
    missing = _parse(candidate.skills_missing) or []
    profile = []
    if candidate.current_role:
        profile.append(f"- **Current role:** {candidate.current_role}")
    if candidate.years_experience is not None:
        profile.append(f"- **Experience:** {candidate.years_experience} years")
    if companies:
        profile.append("- **Companies:** " + ", ".join(str(c) for c in companies))
    if matched:
        profile.append("- **Matched skills:** " + ", ".join(str(s) for s in matched))
    if missing:
        profile.append("- **Missing skills:** " + ", ".join(str(s) for s in missing))
    if candidate.iq_score is not None:
        iq = f"- **Aptitude (IQ) screen:** {round(candidate.iq_score)}%"
        if candidate.iq_total:
            iq += f" ({candidate.iq_correct}/{candidate.iq_total}"
            iq += f", {candidate.iq_time_seconds}s)" if candidate.iq_time_seconds is not None else ")"
        profile.append(iq)
    if profile:
        L += ["", "## Profile"] + profile

    L += ["", "## AI interview"]
    if not interview.get("has_interview"):
        L.append("_No interview conducted yet._")
    else:
        sess = interview.get("session") or {}
        L += [f"- Role: {sess.get('role_type')}", f"- Status: {sess.get('status')}"]
        oa = _parse(sess.get("overall_assessment"))
        ov = (oa or {}).get("overall_assessment") if isinstance(oa, dict) else None
        fr = (oa or {}).get("final_ai_recommendation") if isinstance(oa, dict) else None
        if isinstance(fr, dict):
            if fr.get("decision"):
                L.append(f"- **AI Recommendation: {fr['decision']}**")
            if fr.get("overall_candidate_score") is not None:
                L.append(f"- Overall Candidate Score: {fr['overall_candidate_score']}/100")
            if fr.get("job_match_percentage") is not None:
                L.append(f"- Job Match: {fr['job_match_percentage']}%")
            if fr.get("decision_rationale"):
                L.append(f"- Rationale: {fr['decision_rationale']}")
            for label, key in (("Key Strengths", "key_strengths"), ("Development Areas", "development_areas")):
                vals = fr.get(key) or []
                if vals:
                    L.append(f"- {label}: " + "; ".join(str(v) for v in vals))
        elif isinstance(ov, dict):
            if ov.get("hiring_recommendation"):
                L.append(f"- **AI Recommendation: {ov['hiring_recommendation']}**")
            if ov.get("overall_candidate_score") is not None:
                L.append(f"- Overall Candidate Score: {ov['overall_candidate_score']}/100")
            if ov.get("job_match_percentage") is not None:
                L.append(f"- Job Match: {ov['job_match_percentage']}%")
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


# ==========================================
# AVAILABILITY SCHEDULING
# ==========================================

@app.get("/availability/{token}")
def get_availability_form(token: str, db: Session = Depends(get_db)):
    """Public — candidate fetches their availability form via a signed token."""
    from .availability_tokens import verify_availability_token, generate_availability_slots
    try:
        candidate_id = verify_availability_token(token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    job = cand.job
    return {
        "candidate_name": cand.name,
        "job_title": job.title if job else "Position",
        "org_name": job.org.name if job and job.org else None,
        "org_color": job.org.primary_color if job and job.org else "#1C99BF",
        "slots": generate_availability_slots(),
        "already_submitted": cand.availability_submitted_at is not None,
        "submitted_slot": cand.availability_response,
        "confirmed_slot": cand.interview_confirmed_slot,
    }


@app.post("/availability/{token}")
def submit_availability(token: str, body: AvailabilitySubmit, db: Session = Depends(get_db)):
    """Public — candidate submits their preferred interview time."""
    from .availability_tokens import verify_availability_token
    try:
        candidate_id = verify_availability_token(token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if cand.availability_submitted_at:
        raise HTTPException(status_code=409, detail="Availability already submitted.")
    chosen = (body.selected_slot or body.custom_time or "").strip()
    if not chosen:
        raise HTTPException(status_code=422, detail="No time slot provided.")
    cand.availability_response = chosen
    cand.availability_submitted_at = _utcnow().isoformat()
    db.commit()
    return {"ok": True, "slot": chosen}


@app.get("/interview-room/{token}")
def get_interview_room(token: str, db: Session = Depends(get_db)):
    """Public — candidate fetches their interview room info via a signed interview token."""
    from .interview_links import verify_link, InviteTokenError
    try:
        claims = verify_link(token)
    except InviteTokenError as e:
        raise HTTPException(status_code=400, detail=str(e))
    cand = db.query(Candidate).filter(Candidate.id == claims.candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    job = cand.job
    org = job.org if job else None
    return {
        "candidate_name": cand.name,
        "job_title": job.title if job else "Position",
        "org_name": org.name if org else None,
        "org_color": org.primary_color if org else "#1C99BF",
        "org_logo_url": org.logo_url if org else None,
        "confirmed_slot": cand.interview_confirmed_slot,
        "interview_token": token,
    }


@app.patch("/candidates/{candidate_id}/confirm-slot", response_model=CandidateResponse)
def confirm_interview_slot(
    candidate_id: int,
    body: SlotConfirm,
    db: Session = Depends(get_db),
):
    """HR action: confirm a specific interview slot for a candidate.

    Mints a time-limited interview link, saves the token on the candidate,
    and emails the candidate a confirmation with their interview room URL.
    """
    cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    slot = (body.slot or cand.availability_response or "").strip()
    if not slot:
        raise HTTPException(status_code=422, detail="No slot to confirm.")

    job = cand.job
    if not job:
        raise HTTPException(status_code=400, detail="Candidate is not linked to a job.")

    # Mint an interview link (long TTL — 7 days — so it survives until the interview).
    from .interview_links import mint_link
    token, _interview_url = mint_link(cand.id, job.id, ttl_minutes=7 * 24 * 60)
    base = os.getenv("WEB_BASE_URL", "http://localhost:3000").rstrip("/")
    room_url = f"{base}/interview-room/{token}"

    cand.interview_confirmed_slot = slot
    cand.interview_confirmed_at = _utcnow().isoformat()
    cand.interview_token = token
    cand.interview_invited_at = _utcnow().isoformat()
    db.commit()

    if cand.email:
        try:
            from .services.email import send_slot_confirmation
            send_slot_confirmation(
                to=cand.email,
                candidate_name=cand.name,
                job_title=job.title,
                slot=slot,
                room_url=room_url,
            )
        except Exception as e_mail:
            logger.error("Failed to send slot confirmation to %s: %s", cand.email, e_mail)

    db.refresh(cand)
    return cand


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
