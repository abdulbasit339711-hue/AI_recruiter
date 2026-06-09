import time

import pytest

from recruiter_shared import (
    normalize_role_type,
    mint_invite_token,
    verify_invite_token,
    InviteTokenError,
    is_interview_eligible,
    SHORTLISTED,
)

SECRET = "test-secret"


def test_normalize_role_type():
    assert normalize_role_type("Backend Engineer") == "backend_engineer"
    assert normalize_role_type("  Data  Scientist ") == "data_scientist"
    assert normalize_role_type("Frontend") == "frontend_engineer"  # alias
    assert normalize_role_type("") == ""
    assert normalize_role_type(None) == ""


def test_status_eligibility():
    assert is_interview_eligible(SHORTLISTED)
    assert is_interview_eligible("Processed")  # legacy alias
    assert not is_interview_eligible("Rejected")


def test_token_roundtrip():
    tok = mint_invite_token(42, 7, SECRET, ttl_minutes=10)
    claims = verify_invite_token(tok, SECRET)
    assert claims.candidate_id == 42
    assert claims.job_id == 7
    assert claims.jti


def test_token_expired():
    tok = mint_invite_token(1, 1, SECRET, ttl_minutes=10, now=int(time.time()) - 3600)
    with pytest.raises(InviteTokenError):
        verify_invite_token(tok, SECRET)


def test_token_wrong_secret():
    tok = mint_invite_token(1, 1, SECRET)
    with pytest.raises(InviteTokenError):
        verify_invite_token(tok, "other-secret")


def test_slot_window():
    # slot 1 hour from now -> not yet valid
    tok = mint_invite_token(1, 1, SECRET, slot_at=int(time.time()) + 3600)
    with pytest.raises(InviteTokenError):
        verify_invite_token(tok, SECRET)
    # slot now -> valid within ±5 min
    tok2 = mint_invite_token(1, 1, SECRET, slot_at=int(time.time()))
    assert verify_invite_token(tok2, SECRET).slot_at is not None
