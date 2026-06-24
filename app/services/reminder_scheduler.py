"""Background scheduler: sends interview room link 30 minutes before the confirmed slot."""
import datetime
import logging
import os
import re
import threading
import time

logger = logging.getLogger(__name__)

PKT = datetime.timezone(datetime.timedelta(hours=5))

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
# Slot pattern: "Monday, Jun 30 at 9:00 AM PKT" or "Monday, Jun 30 at 09:00 AM PKT"
_SLOT_RE = re.compile(
    r"\w+,\s+(\w{3})\s+(\d{1,2})\s+at\s+(\d{1,2}):(\d{2})\s+(AM|PM)\s+PKT",
    re.IGNORECASE,
)
# Send window: 25–40 minutes before the slot so a scheduler tick that's a
# little late or early still fires exactly once.
_WINDOW_EARLY_MIN = 40
_WINDOW_LATE_MIN = 25


def _parse_slot_utc(slot_str: str) -> datetime.datetime | None:
    m = _SLOT_RE.search(slot_str)
    if not m:
        return None
    month_abbr, day, hour, minute, ampm = m.groups()
    month = _MONTH_MAP.get(month_abbr.lower())
    if not month:
        return None
    hour, day, minute = int(hour), int(day), int(minute)
    if ampm.upper() == "PM" and hour != 12:
        hour += 12
    elif ampm.upper() == "AM" and hour == 12:
        hour = 0
    now_pkt = datetime.datetime.now(PKT)
    year = now_pkt.year
    try:
        dt_pkt = datetime.datetime(year, month, day, hour, minute, tzinfo=PKT)
        if dt_pkt < now_pkt - datetime.timedelta(days=1):
            dt_pkt = datetime.datetime(year + 1, month, day, hour, minute, tzinfo=PKT)
        return dt_pkt.astimezone(datetime.timezone.utc)
    except ValueError:
        return None


def _run_tick() -> None:
    from ..database import SessionLocal
    from ..models import Candidate
    db = SessionLocal()
    try:
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        candidates = (
            db.query(Candidate)
            .filter(
                Candidate.interview_confirmed_slot.isnot(None),
                Candidate.interview_token.isnot(None),
                Candidate.interview_link_sent_at.is_(None),
                Candidate.email.isnot(None),
            )
            .all()
        )
        for cand in candidates:
            slot_utc = _parse_slot_utc(cand.interview_confirmed_slot or "")
            if slot_utc is None:
                logger.warning("[reminder] Could not parse slot '%s' for candidate %d", cand.interview_confirmed_slot, cand.id)
                continue
            minutes_until = (slot_utc - now_utc).total_seconds() / 60
            if _WINDOW_LATE_MIN <= minutes_until <= _WINDOW_EARLY_MIN:
                _send_reminder(db, cand)
    except Exception as e:
        logger.error("[reminder] tick error: %s", e)
    finally:
        db.close()


def _send_reminder(db, cand) -> None:
    try:
        base = os.getenv("WEB_BASE_URL", "http://localhost:3000").rstrip("/")
        room_url = f"{base}/interview-room/{cand.interview_token}"
        job = cand.job
        org = job.org if job and hasattr(job, "org") else None
        from ..services.email import send_interview_invite
        send_interview_invite(
            to=cand.email,
            candidate_name=cand.name,
            job_title=job.title if job else "your role",
            link=room_url,
            org_name=org.name if org else None,
            org_color=org.primary_color if org else "#1C99BF",
        )
        cand.interview_link_sent_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        db.commit()
        logger.info("[reminder] Interview link sent to candidate %d (%s) for slot '%s'", cand.id, cand.email, cand.interview_confirmed_slot)
    except Exception as e:
        logger.error("[reminder] Failed to send link for candidate %d: %s", cand.id, e)


_stop_event = threading.Event()
_thread: threading.Thread | None = None


def _loop() -> None:
    logger.info("[reminder] Scheduler started (checks every 60s)")
    while not _stop_event.is_set():
        _run_tick()
        _stop_event.wait(timeout=60)
    logger.info("[reminder] Scheduler stopped")


def start_reminder_scheduler() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, name="reminder-scheduler", daemon=True)
    _thread.start()


def stop_reminder_scheduler() -> None:
    _stop_event.set()
    if _thread:
        _thread.join(timeout=5)
