import asyncio
import json
import os
from datetime import datetime
from math import ceil
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy import text
from sqlalchemy.orm import Session

from .core.logging_config import setup_logging
from .core import status as S
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
)
from .queue.worker import enqueue_candidate, start_worker, stop_worker, get_queue_stats
from .llm.groq_client import groq_circuit_state, get_groq_client
from .events.broadcaster import event_hub
from .events.sse import stream_candidate_events, stream_job_events
from .events import publish_candidate_event

load_dotenv()
setup_logging(config.get("logging", {}).get("level", "INFO"))

app = FastAPI(title="AI Recruiter API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    event_hub.bind_loop(asyncio.get_running_loop())
    Base.metadata.create_all(bind=engine)
    run_migrations()
    start_worker()
    get_groq_client()
    # Load heavy sentence‑transformer embedding model once at startup to avoid first‑request latency
    from .core.model_registry import get_embedding_model
    get_embedding_model()


@app.on_event("shutdown")
def on_shutdown():
    stop_worker()


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
            created_at=datetime.utcnow().isoformat(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database write failed: {str(e)}")


@app.get("/jobs")
def list_jobs(status: Optional[str] = "Active", db: Session = Depends(get_db)):
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    return query.all()


@app.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database update failed: {str(e)}")


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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database update failed: {str(e)}")


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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database delete failed: {str(e)}")


# ==========================================
# UPLOAD (immediate response + background queue)
# ==========================================

@app.post("/upload")
async def upload_resume(
    job_id: int = Query(..., description="Target Job ID"),
    file: UploadFile = File(...),
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
            created_at=datetime.utcnow().isoformat(),
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        enqueue_candidate(candidate.id)
        publish_candidate_event(
            candidate.id,
            S.QUEUED,
            job_id=job_id,
            event="queued",
        )

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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


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


@app.patch("/candidates/{candidate_id}/status", response_model=CandidateResponse)
def update_candidate_status(
    candidate_id: int,
    payload: StatusUpdateRequest,
    db: Session = Depends(get_db),
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    
    history = []
    if candidate.status_history:
        try:
            history = json.loads(candidate.status_history)
        except Exception:
            pass
    
    new_entry = {
        "type": "status_change",
        "status": payload.hr_status,
        "changed_by": payload.changed_by,
        "changed_at": datetime.utcnow().isoformat() + "Z",
        "note": payload.note
    }
    history.append(new_entry)
    
    candidate.hr_status = payload.hr_status
    candidate.status_history = json.dumps(history)
    
    try:
        db.commit()
        db.refresh(candidate)
        return candidate
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database update failed: {str(e)}")


@app.post("/candidates/{candidate_id}/notes", response_model=CandidateResponse)
def add_candidate_note(
    candidate_id: int,
    payload: NoteRequest,
    db: Session = Depends(get_db),
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    
    timestamp_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    formatted_note = f"[{timestamp_str}] {payload.author}: {payload.note}"
    
    if candidate.hr_notes:
        candidate.hr_notes = f"{candidate.hr_notes}\n{formatted_note}"
    else:
        candidate.hr_notes = formatted_note
    
    try:
        db.commit()
        db.refresh(candidate)
        return candidate
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database update failed: {str(e)}")


@app.patch("/candidates/{candidate_id}/score-override", response_model=CandidateResponse)
def override_candidate_score(
    candidate_id: int,
    payload: ScoreOverrideRequest,
    db: Session = Depends(get_db),
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    
    history = []
    if candidate.status_history:
        try:
            history = json.loads(candidate.status_history)
        except Exception:
            pass
    
    new_entry = {
        "type": "score_override",
        "status": f"Score Overridden: {payload.override_score}",
        "changed_by": payload.changed_by,
        "changed_at": datetime.utcnow().isoformat() + "Z",
        "note": payload.reason
    }
    history.append(new_entry)
    
    candidate.hr_score_override = payload.override_score
    candidate.status_history = json.dumps(history)
    
    try:
        db.commit()
        db.refresh(candidate)
        return candidate
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database update failed: {str(e)}")


@app.get("/candidates/{candidate_id}/timeline", response_model=TimelineResponse)
def get_candidate_timeline(
    candidate_id: int,
    db: Session = Depends(get_db),
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    
    history = []
    if candidate.status_history:
        try:
            history = json.loads(candidate.status_history)
        except Exception:
            pass
    
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
    enqueue_candidate(candidate_id)
    db.refresh(candidate)
    return {
        "id": candidate.id,
        "status": candidate.status,
        "message": "Reprocessing queued.",
    }


@app.post("/jobs/{job_id}/reprocess")
def reprocess_all_for_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    candidates = db.query(Candidate).filter(Candidate.job_id == job_id).all()
    for cand in candidates:
        cand.status = S.QUEUED
        db.commit()
        enqueue_candidate(cand.id)
    return {
        "message": f"Queued {len(candidates)} candidates for reprocessing.",
        "count": len(candidates),
    }


@app.post("/jobs/{job_id}/email")
def send_shortlist_emails_api(
    job_id: int,
    top_n: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    import smtplib
    from email.message import EmailMessage

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
        return {"message": "No shortlisted candidates to email."}

    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")
    if not smtp_email or not smtp_password:
        raise HTTPException(status_code=500, detail="SMTP credentials not configured.")

    limit = top_n if top_n is not None else len(shortlisted)
    sent_count = 0
    errors = []

    for cand in shortlisted[:limit]:
        if not cand.email:
            errors.append(f"{cand.filename}: no email address.")
            continue
        try:
            msg = EmailMessage()
            msg["From"] = smtp_email
            msg["To"] = cand.email
            msg["Subject"] = f"Your Application for {job.title} – Shortlisted"
            name = cand.name or cand.filename.replace("_", " ")
            body = (
                f"Dear {name},\n\n"
                f"You have been shortlisted for {job.title}.\n\n"
                "Our team will contact you shortly.\n\n"
                "Best regards,\nAI Recruiter Team"
            )
            msg.set_content(body)
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(smtp_email, smtp_password)
                server.send_message(msg)
            sent_count += 1
        except Exception as e:
            errors.append(f"{cand.email}: {str(e)}")

    return {
        "message": f"Sent {sent_count} emails.",
        "failed_count": len(errors),
        "errors": errors,
    }
