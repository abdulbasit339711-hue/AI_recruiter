"""HMAC-signed availability-form tokens (72-hour default TTL)."""
import base64
import hashlib
import hmac
import json
import os
import time


def _secret() -> str:
    return (os.getenv("INTERVIEW_LINK_SECRET") or "availability-dev-secret").strip()


def mint_availability_token(candidate_id: int, ttl_hours: int = 72) -> tuple[str, str]:
    """Return (token, full_url) for a candidate's availability form."""
    exp = int(time.time()) + ttl_hours * 3600
    payload = json.dumps({"sub": candidate_id, "exp": exp}, separators=(",", ":"))
    b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig = hmac.new(_secret().encode(), b64.encode(), hashlib.sha256).hexdigest()[:24]
    token = f"{b64}.{sig}"
    base_url = os.getenv("WEB_BASE_URL", "http://localhost:3000").rstrip("/")
    return token, f"{base_url}/availability/{token}"


def verify_availability_token(token: str) -> int:
    """Return candidate_id or raise ValueError."""
    try:
        b64, sig = token.rsplit(".", 1)
    except ValueError:
        raise ValueError("Invalid token format")
    expected = hmac.new(_secret().encode(), b64.encode(), hashlib.sha256).hexdigest()[:24]
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Invalid signature")
    try:
        padded = b64 + "=" * (4 - len(b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
    except Exception:
        raise ValueError("Invalid payload")
    if payload.get("exp", 0) < time.time():
        raise ValueError("Token expired")
    return int(payload["sub"])


PKT = __import__("datetime").timezone(__import__("datetime").timedelta(hours=5))
_SLOT_HOURS = [9, 10, 11, 14, 15, 16]


def generate_availability_slots(n_days: int = 10) -> list[str]:
    """Generate interview slot strings for the next n_days business days in PKT."""
    import datetime
    slots = []
    now = datetime.datetime.now(PKT)
    day = now.date() + datetime.timedelta(days=1)
    business_days = 0
    while business_days < n_days:
        if day.weekday() < 5:  # Mon-Fri only
            for hour in _SLOT_HOURS:
                dt = datetime.datetime(day.year, day.month, day.day, hour, 0, tzinfo=PKT)
                label = f"{dt.strftime('%A, %b')} {dt.day} at {dt.strftime('%I:%M %p')} PKT"
                slots.append(label)
            business_days += 1
        day += datetime.timedelta(days=1)
    return slots
