import json
from datetime import datetime, timezone

from .tokens import verify_result_token


def attach_iq_result(db, candidate, result_token: str, job_id: int) -> str | None:
    """Copy a signed IQ result onto ``candidate``. Returns None on success, else why it was refused.

    Raises IqTokenError for a bad/expired token. Single-use: one result (jti) can't be replayed."""
    from ..models import Candidate

    res = verify_result_token(result_token)
    if res.job_id != job_id:
        return "job mismatch"
    if res.jti and db.query(Candidate.id).filter(Candidate.iq_result_jti == res.jti).first():
        return "result already used"
    candidate.iq_score = res.score
    candidate.iq_correct = res.correct
    candidate.iq_total = res.total
    candidate.iq_time_seconds = res.time_seconds
    candidate.iq_details = json.dumps(res.detail) if res.detail else None
    candidate.iq_result_jti = res.jti or None
    candidate.iq_attempted_at = datetime.fromtimestamp(res.iat, tz=timezone.utc).isoformat()
    return None
