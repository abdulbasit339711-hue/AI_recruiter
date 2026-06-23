import time as _time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.ratelimit import iq_rate_limit
from ..core.utils import _utcnow
from ..database import get_db, config
from ..models import Job
from ..iq import (
    sample_questions,
    score_answers,
    time_adjusted_score,
    build_detail,
    mint_test_token,
    verify_test_token,
    mint_result_token,
    IqTokenError,
)
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
