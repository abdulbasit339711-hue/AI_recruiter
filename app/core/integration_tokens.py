"""Per-customer API tokens for the HR platform (HRMS) integration.

Each token is bound to ONE org (customer). It is stored only as a SHA-256 hash (the
plaintext is shown once at creation), can be revoked individually, and only opens a
small allowlist of routes, each limited to that org's jobs/candidates. The shared
``ADMIN_API_TOKEN`` keeps working unchanged for the HR dashboard.
"""

import hashlib
import re
import secrets

from sqlalchemy import Column, ForeignKey, Integer, String

from ..database import Base, SessionLocal
from .utils import _utcnow

_PREFIX = "air_"


class IntegrationToken(Base):
    __tablename__ = "integration_tokens"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    token_hash = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(String, nullable=False)
    last_used_at = Column(String, nullable=True)
    revoked_at = Column(String, nullable=True)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_token(db, org_id: int, name: str) -> tuple[IntegrationToken, str]:
    plain = _PREFIX + secrets.token_urlsafe(32)
    row = IntegrationToken(org_id=org_id, name=name, token_hash=_hash(plain), created_at=_utcnow().isoformat())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, plain


def org_for_authorization(authorization: str | None) -> int | None:
    """Org id for an active integration token in an ``Authorization: Bearer`` header, else None."""
    if not authorization:
        return None
    scheme, _, presented = authorization.partition(" ")
    presented = presented.strip()
    if scheme.lower() != "bearer" or not presented.startswith(_PREFIX):
        return None
    db = SessionLocal()
    try:
        row = db.query(IntegrationToken).filter(
            IntegrationToken.token_hash == _hash(presented), IntegrationToken.revoked_at.is_(None)
        ).first()
        if not row:
            return None
        row.last_used_at = _utcnow().isoformat()
        db.commit()
        return row.org_id
    finally:
        db.close()


# (method, path regex, what the first path id refers to). POST /jobs has no id: the route
# forces the new job into the token's org (see jobs.create_job).
_ALLOWED = (
    ("POST", re.compile(r"^/jobs/?$"), None),
    ("GET", re.compile(r"^/jobs/(\d+)/candidates/?$"), "job"),
    ("GET", re.compile(r"^/candidates/(\d+)/?$"), "candidate"),
    ("POST", re.compile(r"^/candidates/(\d+)/interview-invite/?$"), "candidate"),
)


def integration_allowed(org_id: int, method: str, path: str) -> bool:
    """True if this org's token may call (method, path) — allowlisted AND the target belongs to the org."""
    from ..models import Candidate, Job

    for m, rx, kind in _ALLOWED:
        match = rx.match(path)
        if m != method or not match:
            continue
        if kind is None:
            return True
        db = SessionLocal()
        try:
            rid = int(match.group(1))
            if kind == "job":
                job = db.query(Job).filter(Job.id == rid).first()
            else:
                cand = db.query(Candidate).filter(Candidate.id == rid).first()
                job = db.query(Job).filter(Job.id == cand.job_id).first() if cand else None
            return bool(job and job.org_id == org_id)
        finally:
            db.close()
    return False
