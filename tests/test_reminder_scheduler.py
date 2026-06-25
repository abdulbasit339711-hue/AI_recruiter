"""Tests for app/services/reminder_scheduler.py

Covers:
- Slot-string parsing (_parse_slot_utc)
- Tick selection: only candidates whose slot falls in the 25–40 min window
- Skip candidates that already have interview_link_sent_at set
- _send_reminder stamps interview_link_sent_at and calls send_interview_invite
"""

import datetime
from unittest.mock import MagicMock, call, patch

import pytest

from app.database import SessionLocal
from app.models import Candidate, Job
from app.services.reminder_scheduler import (
    PKT,
    _parse_slot_utc,
    _run_tick,
    _send_reminder,
)


# ── Slot parser ─────────────────────────────────────────────────────────────────

def _pkt_now():
    return datetime.datetime.now(PKT)


def _slot_str(dt_pkt: datetime.datetime) -> str:
    """Format a PKT datetime the way the availability router writes it."""
    ampm = "AM" if dt_pkt.hour < 12 else "PM"
    h = dt_pkt.hour % 12 or 12
    return dt_pkt.strftime(f"%A, %b {dt_pkt.day} at {h}:{dt_pkt.strftime('%M')} {ampm} PKT")


def test_parse_slot_utc_round_trips():
    target = _pkt_now().replace(microsecond=0, second=0) + datetime.timedelta(hours=2)
    parsed = _parse_slot_utc(_slot_str(target))
    assert parsed is not None
    # Round-trip: parsed UTC → PKT should match original (minute precision)
    assert parsed.astimezone(PKT).replace(second=0) == target


def test_parse_slot_utc_pm_conversion():
    dt = _pkt_now().replace(hour=14, minute=30, second=0, microsecond=0)
    parsed = _parse_slot_utc(_slot_str(dt))
    assert parsed is not None
    assert parsed.astimezone(PKT).hour == 14


def test_parse_slot_utc_midnight_edge():
    dt = _pkt_now().replace(hour=0, minute=0, second=0, microsecond=0)
    parsed = _parse_slot_utc(_slot_str(dt))
    assert parsed is not None
    assert parsed.astimezone(PKT).hour == 0


def test_parse_slot_utc_returns_none_for_garbage():
    assert _parse_slot_utc("") is None
    assert _parse_slot_utc("some random text") is None
    assert _parse_slot_utc("Monday, Xyz 5 at 9:00 AM PKT") is None  # bad month


# ── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def job(db):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    j = Job(title="Backend Engineer", department="Eng",
            job_description="Python role", status="Active", created_at=now)
    db.add(j)
    db.commit()
    yield j
    db.delete(j)
    db.commit()


def _make_candidate(db, job, *, minutes_from_now: float,
                    link_sent: bool = False, token: str = "tok123",
                    email: str = "c@example.com") -> Candidate:
    slot_dt = _pkt_now().replace(second=0, microsecond=0) + datetime.timedelta(minutes=minutes_from_now)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    c = Candidate(
        filename="cv.pdf",
        email=email,
        raw_text="resume",
        job_id=job.id,
        created_at=now,
        interview_confirmed_slot=_slot_str(slot_dt),
        interview_token=token,
        interview_link_sent_at=now if link_sent else None,
    )
    db.add(c)
    db.commit()  # commit so _run_tick's own SessionLocal sees the row
    return c


# ── Tick selection logic ─────────────────────────────────────────────────────────

def test_tick_sends_to_candidate_in_window(db, job):
    """Candidate with slot 30 min away (inside 25–40 min window) gets the email."""
    cand = _make_candidate(db, job, minutes_from_now=30)

    smtp_cls, server = MagicMock(), MagicMock()
    smtp_cls.return_value.__enter__.return_value = server
    with patch("app.services.email.smtplib.SMTP", smtp_cls), \
         patch.dict("os.environ", {"SMTP_EMAIL": "r@x.com", "SMTP_PASSWORD": "pw",
                                   "WEB_BASE_URL": "https://app.example.com"}):
        _run_tick()

    db.refresh(cand)
    assert cand.interview_link_sent_at is not None   # stamped
    server.send_message.assert_called_once()         # email sent
    db.delete(cand); db.commit()


def test_tick_skips_candidate_outside_window(db, job):
    """Slot is 2 hours away — outside the 25–40 min window, no email."""
    cand = _make_candidate(db, job, minutes_from_now=120)

    smtp_cls = MagicMock()
    with patch("app.services.email.smtplib.SMTP", smtp_cls), \
         patch.dict("os.environ", {"SMTP_EMAIL": "r@x.com", "SMTP_PASSWORD": "pw"}):
        _run_tick()

    db.refresh(cand)
    assert cand.interview_link_sent_at is None       # not sent
    smtp_cls.assert_not_called()
    db.delete(cand); db.commit()


def test_tick_skips_already_sent(db, job):
    """interview_link_sent_at already set — scheduler must not resend."""
    cand = _make_candidate(db, job, minutes_from_now=30, link_sent=True)

    smtp_cls = MagicMock()
    with patch("app.services.email.smtplib.SMTP", smtp_cls), \
         patch.dict("os.environ", {"SMTP_EMAIL": "r@x.com", "SMTP_PASSWORD": "pw"}):
        _run_tick()

    smtp_cls.assert_not_called()
    db.delete(cand); db.commit()


def test_tick_skips_candidate_without_token(db, job):
    """No interview_token → no link to embed, scheduler skips."""
    cand = _make_candidate(db, job, minutes_from_now=30, token=None)

    smtp_cls = MagicMock()
    with patch("app.services.email.smtplib.SMTP", smtp_cls), \
         patch.dict("os.environ", {"SMTP_EMAIL": "r@x.com", "SMTP_PASSWORD": "pw"}):
        _run_tick()

    smtp_cls.assert_not_called()
    db.delete(cand); db.commit()


# ── _send_reminder ───────────────────────────────────────────────────────────────

def test_send_reminder_stamps_link_sent_at(db, job):
    cand = _make_candidate(db, job, minutes_from_now=30)
    db.commit()
    assert cand.interview_link_sent_at is None

    smtp_cls, server = MagicMock(), MagicMock()
    smtp_cls.return_value.__enter__.return_value = server
    with patch("app.services.email.smtplib.SMTP", smtp_cls), \
         patch.dict("os.environ", {"SMTP_EMAIL": "r@x.com", "SMTP_PASSWORD": "pw",
                                   "WEB_BASE_URL": "https://app.example.com"}):
        _send_reminder(db, cand)

    db.refresh(cand)
    assert cand.interview_link_sent_at is not None
    db.delete(cand); db.commit()


def test_send_reminder_email_contains_room_link(db, job):
    cand = _make_candidate(db, job, minutes_from_now=30, token="mytoken42")
    db.commit()

    smtp_cls, server = MagicMock(), MagicMock()
    smtp_cls.return_value.__enter__.return_value = server
    with patch("app.services.email.smtplib.SMTP", smtp_cls), \
         patch.dict("os.environ", {"SMTP_EMAIL": "r@x.com", "SMTP_PASSWORD": "pw",
                                   "WEB_BASE_URL": "https://app.example.com"}):
        _send_reminder(db, cand)

    sent = server.send_message.call_args.args[0]
    # The room URL must contain the candidate's token
    assert "mytoken42" in str(sent)
    assert sent["To"] == "c@example.com"
    db.delete(cand); db.commit()


def test_send_reminder_does_not_crash_on_smtp_error(db, job):
    """SMTP failure must not propagate — scheduler swallows and logs."""
    cand = _make_candidate(db, job, minutes_from_now=30)
    db.commit()

    smtp_cls, server = MagicMock(), MagicMock()
    smtp_cls.return_value.__enter__.return_value = server
    server.send_message.side_effect = RuntimeError("connection reset")
    with patch("app.services.email.smtplib.SMTP", smtp_cls), \
         patch.dict("os.environ", {"SMTP_EMAIL": "r@x.com", "SMTP_PASSWORD": "pw",
                                   "WEB_BASE_URL": "https://app.example.com"}):
        _send_reminder(db, cand)   # must not raise

    db.refresh(cand)
    # link_sent_at should NOT be stamped if send failed
    assert cand.interview_link_sent_at is None
    db.delete(cand); db.commit()
