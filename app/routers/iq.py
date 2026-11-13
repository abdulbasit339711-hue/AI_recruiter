import json
import os
import time as _time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.ratelimit import iq_rate_limit
from ..core.utils import _utcnow
from ..database import get_db, config
from ..models import Candidate, Job, Org
from ..services.email import send_iq_invite
from ..iq import (
    sample_questions,
    score_answers,
    time_adjusted_score,
    build_detail,
    mint_test_token,
    verify_test_token,
    mint_result_token,
    mint_invite_token,
    verify_invite_token,
    IqTokenError,
)
from ..iq.attach import attach_iq_result
from ..iq.models import IqQuestionRow
from ..schemas import IqTestResponse, IqSubmitRequest, IqSubmitResponse

router = APIRouter()


@router.get("/iq-test", response_model=IqTestResponse, dependencies=[Depends(iq_rate_limit)])
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


@router.post("/iq-test/submit", response_model=IqSubmitResponse, dependencies=[Depends(iq_rate_limit)])
def submit_iq_test(payload: IqSubmitRequest, db: Session = Depends(get_db)):
    """Score answers server-side against the bank and issue a signed result token.

    The result token is what the applicant later hands to /upload so the score is
    attached to their candidate row (tamper-proof, so it can ride through the client).
    Each test token (jti) is single-use: resubmitting the same token is rejected so
    a candidate can't fish for the best score by submitting different answers repeatedly.
    """
    try:
        claims = verify_test_token(payload.test_token)
    except IqTokenError as e:
        raise HTTPException(status_code=400, detail=f"Invalid or expired test: {e}")

    # Single-use jti: reject replay across restarts (persisted in DB, not in-memory).
    if db.execute(
        text("SELECT 1 FROM used_iq_test_tokens WHERE jti = :j"),
        {"j": claims.jti},
    ).first():
        raise HTTPException(status_code=400, detail="This test has already been submitted.")

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

    # Mark jti as used AFTER scoring succeeds so a DB error doesn't permanently
    # block the candidate from submitting (they can retry if this fails).
    try:
        db.execute(
            text("INSERT INTO used_iq_test_tokens (jti, used_at) VALUES (:j, :t)"),
            {"j": claims.jti, "t": _utcnow().isoformat()},
        )
        db.commit()
    except Exception:
        db.rollback()

    return {
        "correct": correct,
        "total": total,
        "accuracy": accuracy,
        "score": score,
        "time_seconds": elapsed,
        "detail": detail,
        "result_token": result_token,
    }


# ── HR: send a candidate a standalone IQ-test link ────────────────────────────

_INVITE_TTL_SECONDS = 7 * 24 * 3600


@router.post("/candidates/{candidate_id}/iq-invite")
def send_iq_invite_api(candidate_id: int, db: Session = Depends(get_db)):
    """HR action: email an existing candidate a link to take the IQ test (admin-token protected)."""
    cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if not cand.email:
        raise HTTPException(status_code=400, detail="Candidate has no email address.")
    if cand.iq_score is not None:
        raise HTTPException(status_code=409, detail="Candidate has already taken the IQ test.")
    job = db.query(Job).filter(Job.id == cand.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Candidate is not linked to a job.")
    try:
        token = mint_invite_token(cand.id, job.id, ttl_seconds=_INVITE_TTL_SECONDS)
    except IqTokenError as e:
        raise HTTPException(status_code=503, detail=str(e))
    base = os.getenv("WEB_BASE_URL", "http://localhost:3000").rstrip("/")
    link = f"{base}/iq/{token}"
    org = db.query(Org).filter(Org.id == job.org_id).first() if job.org_id else None
    send_iq_invite(to=cand.email, candidate_name=cand.name, job_title=job.title, link=link,
                   org_name=org.name if org else None)
    return {"status": "sent", "candidate_id": cand.id, "link": link}


def _invite_candidate(db: Session, token: str) -> Candidate:
    try:
        cid, _ = verify_invite_token(token)
    except IqTokenError:
        raise HTTPException(status_code=400, detail="This link is invalid or has expired.")
    cand = db.query(Candidate).filter(Candidate.id == cid).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return cand


@router.get("/iq-invite/{token}", dependencies=[Depends(iq_rate_limit)])
def get_iq_invite(token: str, db: Session = Depends(get_db)):
    """Public: validate an HR-sent link; tells the page which job's test to load."""
    cand = _invite_candidate(db, token)
    job = db.query(Job).filter(Job.id == cand.job_id).first()
    return {
        "job_id": cand.job_id,
        "job_title": job.title if job else "",
        "candidate_name": cand.name,
        "already_taken": cand.iq_score is not None,
    }


class IqAttachRequest(BaseModel):
    result_token: str


@router.post("/iq-invite/{token}/attach", dependencies=[Depends(iq_rate_limit)])
def attach_iq_invite(token: str, payload: IqAttachRequest, db: Session = Depends(get_db)):
    """Public: attach the signed result (from /iq-test/submit) to the invited candidate."""
    cand = _invite_candidate(db, token)
    if cand.iq_score is not None:
        raise HTTPException(status_code=409, detail="The IQ test was already taken.")
    try:
        why = attach_iq_result(db, cand, payload.result_token, cand.job_id)
    except IqTokenError as e:
        raise HTTPException(status_code=400, detail=f"Invalid result: {e}")
    if why:
        raise HTTPException(status_code=409, detail=f"Result not accepted ({why}).")
    db.commit()
    return {"status": "recorded"}


# ── HR: manage the IQ question bank (admin-token protected) ────────────────────

class IqQuestionIn(BaseModel):
    prompt: str = Field(min_length=3, max_length=500)
    options: list[str] = Field(min_length=2, max_length=6)
    answer: int
    active: bool = True

    @field_validator("options")
    @classmethod
    def _opts(cls, v):
        v = [o.strip() for o in v]
        if any(not o for o in v):
            raise ValueError("options must be non-empty")
        return v

    @field_validator("answer")
    @classmethod
    def _ans(cls, v, info):
        n = len(info.data.get("options") or [])
        if not 0 <= v < n:
            raise ValueError("answer must index into options")
        return v


def _row_out(r: IqQuestionRow) -> dict:
    return {"id": r.id, "prompt": r.prompt, "options": json.loads(r.options), "answer": r.answer, "active": bool(r.active)}


@router.get("/iq-questions")
def list_iq_questions(db: Session = Depends(get_db)):
    """HR-authored questions (the built-in bank is always served too)."""
    return [_row_out(r) for r in db.query(IqQuestionRow).order_by(IqQuestionRow.id).all()]


@router.post("/iq-questions", status_code=201)
def create_iq_question(body: IqQuestionIn, db: Session = Depends(get_db)):
    r = IqQuestionRow(prompt=body.prompt.strip(), options=json.dumps(body.options), answer=body.answer,
                      active=body.active, created_at=_utcnow().isoformat())
    db.add(r)
    db.commit()
    db.refresh(r)
    return _row_out(r)


@router.put("/iq-questions/{qid}")
def update_iq_question(qid: int, body: IqQuestionIn, db: Session = Depends(get_db)):
    r = db.query(IqQuestionRow).filter(IqQuestionRow.id == qid).first()
    if not r:
        raise HTTPException(status_code=404, detail="Question not found.")
    r.prompt, r.options, r.answer, r.active = body.prompt.strip(), json.dumps(body.options), body.answer, body.active
    db.commit()
    return _row_out(r)


@router.delete("/iq-questions/{qid}", status_code=204)
def delete_iq_question(qid: int, db: Session = Depends(get_db)):
    """Soft-delete: stops serving it; tests already in flight still score."""
    r = db.query(IqQuestionRow).filter(IqQuestionRow.id == qid).first()
    if not r:
        raise HTTPException(status_code=404, detail="Question not found.")
    r.active = False
    db.commit()
