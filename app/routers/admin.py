import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from ..core import status as S
from ..core.jd_embedding_cache import cache_stats
from ..core.model_registry import models_loaded
from ..core.utils import _utcnow
from ..database import get_db, DATABASE_URL
from ..llm.groq_client import groq_circuit_state
from ..models import Candidate, Job, Org, Setting
from ..queue.worker import get_queue_stats
from .jobs import _serialize_job, _serialize_org

logger = logging.getLogger(__name__)

router = APIRouter()

_SETTING_DEFS: dict[str, dict] = {
    "availability_threshold": {
        "label": "Availability Invite Threshold",
        "description": "Minimum total score (0–100) a candidate must reach before the system auto-sends them the interview availability form.",
        "type": "number",
        "min": 0,
        "max": 100,
    },
}


@router.get("/")
def read_root():
    return {"message": "AI Recruiter API is running.", "version": "2.0.0"}


@router.get("/health")
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


@router.get("/metrics")
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

    # Shortlisted by AI but HR hasn't taken any action yet (no status change beyond "Applied" or null).
    pending_review = (
        _q(Candidate)
        .filter(Candidate.status.in_([S.SHORTLISTED, S.REVIEWED, "Shortlisted", "Reviewed"]))
        .filter(Candidate.hr_status.in_(["Applied", None]))
        .count()
    )
    # Shortlisted but no interview token — ready to be invited.
    interview_ready = (
        _q(Candidate)
        .filter(Candidate.status.in_([S.SHORTLISTED, "Shortlisted"]))
        .filter(Candidate.interview_token.is_(None))
        .count()
    )
    # Completed AI interview and passed — ready for human 2nd-round.
    interview_passed_count = (
        _q(Candidate)
        .filter(Candidate.interview_passed == True)  # noqa: E712
        .count()
    )

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
        "pendingReviewCount": pending_review,
        "interviewReadyCount": interview_ready,
        "interviewPassedCount": interview_passed_count,
    }


@router.get("/candidates/action-needed")
def get_action_needed_candidates(
    job_id: Optional[int] = Query(None),
    limit: int = Query(8, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Shortlisted candidates without an interview token — ready to be invited."""
    q = (
        db.query(Candidate)
        .filter(Candidate.status.in_([S.SHORTLISTED, "Shortlisted"]))
        .filter(Candidate.interview_token.is_(None))
    )
    if job_id is not None:
        q = q.filter(Candidate.job_id == job_id)
    rows = q.order_by(Candidate.total_score.desc()).limit(limit).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "job_id": c.job_id,
            "total_score": c.total_score,
            "status": c.status,
            "hr_status": c.hr_status,
        }
        for c in rows
    ]


@router.get("/candidates/interview-passed")
def get_interview_passed_candidates(
    job_id: Optional[int] = Query(None),
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Candidates who completed and passed the AI voice interview — ready for human 2nd round."""
    q = db.query(Candidate).filter(Candidate.interview_passed == True)  # noqa: E712
    if job_id is not None:
        q = q.filter(Candidate.job_id == job_id)
    rows = q.order_by(Candidate.interview_overall_score.desc().nullslast()).limit(limit).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "job_id": c.job_id,
            "total_score": c.total_score,
            "interview_phase1_score": c.interview_phase1_score,
            "interview_phase2_score": c.interview_phase2_score,
            "interview_overall_score": c.interview_overall_score,
            "interview_completed_at": c.interview_completed_at,
            "status": c.status,
            "hr_status": c.hr_status,
        }
        for c in rows
    ]


# ==========================================
# ORGS CRUD
# ==========================================

@router.post("/orgs")
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


@router.get("/orgs")
def list_orgs(db: Session = Depends(get_db)):
    return [_serialize_org(o) for o in db.query(Org).order_by(Org.name).all()]


@router.get("/orgs/{slug}")
def get_org(slug: str, db: Session = Depends(get_db)):
    org = db.query(Org).filter(Org.slug == slug).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return _serialize_org(org)


@router.get("/orgs/{slug}/jobs")
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


@router.patch("/orgs/{org_id}")
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


@router.delete("/orgs/{org_id}")
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

@router.get("/settings")
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


@router.patch("/settings/{key}")
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
