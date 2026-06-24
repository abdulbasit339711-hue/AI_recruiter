import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.utils import _utcnow
from ..database import get_db
from ..models import Candidate, Job
from ..schemas import AvailabilitySubmit, CandidateResponse, SlotConfirm

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/availability/{token}")
def get_availability_form(token: str, db: Session = Depends(get_db)):
    """Public — candidate fetches their availability form via a signed token."""
    from ..availability_tokens import verify_availability_token, generate_availability_slots
    try:
        candidate_id = verify_availability_token(token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    job = cand.job

    # Exclude slots already taken by any other candidate (global uniqueness).
    taken = {
        row[0] for row in
        db.query(Candidate.availability_response)
        .filter(
            Candidate.availability_response.isnot(None),
            Candidate.id != candidate_id,
        )
        .all()
    }
    all_slots = generate_availability_slots()
    available = [s for s in all_slots if s not in taken]

    return {
        "candidate_name": cand.name,
        "job_title": job.title if job else "Position",
        "org_name": job.org.name if job and job.org else None,
        "org_color": job.org.primary_color if job and job.org else "#1C99BF",
        "slots": available,
        "already_submitted": cand.availability_submitted_at is not None,
        "submitted_slot": cand.availability_response,
        "confirmed_slot": cand.interview_confirmed_slot,
    }


@router.post("/availability/{token}")
def submit_availability(token: str, body: AvailabilitySubmit, db: Session = Depends(get_db)):
    """Public — candidate submits their preferred interview time."""
    from ..availability_tokens import verify_availability_token
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

    # Reject if another candidate already claimed this slot (race-condition guard).
    conflict = (
        db.query(Candidate.id)
        .filter(Candidate.availability_response == chosen, Candidate.id != candidate_id)
        .first()
    )
    if conflict:
        raise HTTPException(status_code=409, detail="This slot was just taken by another candidate. Please go back and choose a different time.")

    cand.availability_response = chosen
    cand.availability_submitted_at = _utcnow().isoformat()

    # Auto-confirm: no HR action needed.  Mint interview link now (7-day TTL)
    # and send a confirmation email.  The actual room link goes out 30 min
    # before the slot via the reminder scheduler.
    job = cand.job
    if job:
        from ..interview_links import mint_link
        token, _room_url = mint_link(cand.id, job.id, ttl_minutes=7 * 24 * 60)
        cand.interview_confirmed_slot = chosen
        cand.interview_confirmed_at = _utcnow().isoformat()
        cand.interview_token = token
        cand.interview_invited_at = _utcnow().isoformat()
        db.commit()
        if cand.email:
            try:
                from ..services.email import send_slot_confirmation
                org = job.org if hasattr(job, "org") else None
                send_slot_confirmation(
                    to=cand.email,
                    candidate_name=cand.name,
                    job_title=job.title,
                    slot=chosen,
                    room_url=None,
                    org_name=org.name if org else None,
                    org_color=org.primary_color if org else "#1C99BF",
                )
            except Exception as e:
                logger.error("Auto slot-confirmation email failed for candidate %d: %s", cand.id, e)
    else:
        db.commit()

    return {"ok": True, "slot": chosen}


@router.get("/interview-room/{token}")
def get_interview_room(token: str, db: Session = Depends(get_db)):
    """Public — candidate fetches their interview room info via a signed interview token."""
    from ..interview_links import verify_link, InviteTokenError
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


@router.patch("/candidates/{candidate_id}/confirm-slot", response_model=CandidateResponse)
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
    from ..interview_links import mint_link
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
            from ..services.email import send_slot_confirmation
            send_slot_confirmation(
                to=cand.email,
                candidate_name=cand.name,
                job_title=job.title,
                slot=slot,
                room_url=room_url,
                org_name=job.org.name if job.org else None,
                org_color=job.org.primary_color if job.org else "#1C99BF",
            )
        except Exception as e_mail:
            logger.error("Failed to send slot confirmation to %s: %s", cand.email, e_mail)

    db.refresh(cand)
    return cand
