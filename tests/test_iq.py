"""Tests for the pre-application IQ screen (app/iq + endpoints + upload attach).

Covers: bank scoring, signed-token round-trip / tamper / expiry, the two public
endpoints, and that /upload attaches a valid result token's score while NEVER
blocking the application when the token is absent, invalid, or for another job.
"""

import pytest
from fastapi.testclient import TestClient

import time

from app.iq import (
    IqTokenError,
    build_detail,
    get_bank,
    mint_result_token,
    mint_test_token,
    sample_questions,
    score_answers,
    time_adjusted_score,
    verify_result_token,
    verify_test_token,
)
from app.main import app
from app.database import SessionLocal
from app.models import Candidate, Job


# ── Bank ────────────────────────────────────────────────────────────────────────

def test_public_question_hides_answer():
    for q in get_bank():
        pub = q.to_public()
        assert set(pub) == {"id", "prompt", "options"}
        assert "answer" not in pub


def test_sample_is_distinct_and_clamped():
    qs = sample_questions(1000)  # more than the bank holds
    ids = [q.id for q in qs]
    assert len(ids) == len(set(ids)) == len(get_bank())


def test_score_perfect_and_partial():
    qs = sample_questions(5)
    ids = [q.id for q in qs]
    assert score_answers({q.id: q.answer for q in qs}, ids) == (5, 5)
    # one wrong
    answers = {q.id: q.answer for q in qs}
    answers[ids[0]] = (qs[0].answer + 1) % len(qs[0].options)
    assert score_answers(answers, ids) == (4, 5)


def test_time_adjusted_score():
    # accuracy is the ceiling; using more time erodes it by up to speed_weight
    assert time_adjusted_score(8, 10, 0, 600, 0.2) == 80.0      # instant -> full accuracy
    assert time_adjusted_score(8, 10, 300, 600, 0.2) == 72.0    # half time -> 80 * 0.9
    assert time_adjusted_score(8, 10, 600, 600, 0.2) == 64.0    # full time -> 80 * 0.8
    assert time_adjusted_score(0, 10, 0, 600, 0.2) == 0.0       # wrong -> 0 regardless of speed
    assert time_adjusted_score(5, 5, 999, 0, 0.2) == 100.0      # no limit -> pure accuracy


def test_score_ignores_unknown_and_unserved():
    qs = sample_questions(3)
    ids = [q.id for q in qs]
    answers = {q.id: q.answer for q in qs}
    answers["does-not-exist"] = 0          # unknown id can't inflate
    correct, total = score_answers(answers, ids + ["does-not-exist"])
    # total counts served ids (incl. the bogus one) but the bogus one is never correct
    assert (correct, total) == (3, 4)


# ── Tokens ──────────────────────────────────────────────────────────────────────

def test_test_token_round_trip():
    tok = mint_test_token(7, ["a", "b"], ttl_seconds=600)
    claims = verify_test_token(tok)
    assert claims.job_id == 7 and claims.question_ids == ["a", "b"]


def test_result_token_round_trip():
    tok = mint_result_token(7, 4, 5, 80.0, ttl_seconds=3600)
    claims = verify_result_token(tok)
    assert (claims.job_id, claims.correct, claims.total, claims.score) == (7, 4, 5, 80.0)


def test_tampered_token_rejected():
    tok = mint_result_token(7, 4, 5, 80.0, ttl_seconds=3600)
    with pytest.raises(IqTokenError):
        verify_result_token(tok + "x")


def test_expired_token_rejected():
    tok = mint_test_token(7, ["a"], ttl_seconds=-60)  # well past the leeway
    with pytest.raises(IqTokenError):
        verify_test_token(tok)


def test_wrong_token_type_rejected():
    test_tok = mint_test_token(7, ["a"], ttl_seconds=600)
    with pytest.raises(IqTokenError):
        verify_result_token(test_tok)  # a test token is not a result token


# ── Endpoints + upload ──────────────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)  # keep the apply flow public
    monkeypatch.setattr("app.main.validate_and_extract", lambda *_a: "resume text")
    monkeypatch.setattr("app.main.enqueue_candidate", lambda _cid: None)
    return TestClient(app)


def _make_job(title="IQ Job") -> int:
    db = SessionLocal()
    try:
        j = Job(title=title, department="Eng", job_description="jd",
                status="Active", created_at="2026-06-12T00:00:00")
        db.add(j); db.commit(); db.refresh(j)
        return j.id
    finally:
        db.close()


def _upload(client, job_id, iq_token=None):
    data = {"iq_token": iq_token} if iq_token is not None else None
    return client.post(
        "/upload",
        params={"job_id": job_id},
        files={"file": ("resume.pdf", b"fake pdf bytes", "application/pdf")},
        data=data,
    )


def _candidate(cid) -> Candidate:
    db = SessionLocal()
    try:
        return db.query(Candidate).filter(Candidate.id == cid).first()
    finally:
        db.close()


def test_get_iq_test_returns_questions_without_answers(client):
    jid = _make_job()
    r = client.get(f"/iq-test?job_id={jid}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == len(body["questions"]) > 0
    assert all("answer" not in q for q in body["questions"])
    assert body["test_token"]


def test_get_iq_test_unknown_job_404(client):
    assert client.get("/iq-test?job_id=999999").status_code == 404


def test_submit_scores_and_issues_result(client):
    jid = _make_job()
    test = client.get(f"/iq-test?job_id={jid}").json()
    # answer everything with index 0 (deterministic, partial score)
    answers = {q["id"]: 0 for q in test["questions"]}
    r = client.post("/iq-test/submit", json={"test_token": test["test_token"], "answers": answers})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == test["total"]
    assert 0 <= body["score"] <= 100
    assert body["result_token"]


def test_submit_bad_token_400(client):
    assert client.post("/iq-test/submit", json={"test_token": "nope", "answers": {}}).status_code == 400


def test_submit_response_has_accuracy_and_time(client):
    jid = _make_job()
    test = client.get(f"/iq-test?job_id={jid}").json()
    answers = {q["id"]: 0 for q in test["questions"]}
    body = client.post("/iq-test/submit", json={"test_token": test["test_token"], "answers": answers}).json()
    assert {"correct", "total", "accuracy", "score", "time_seconds", "detail", "result_token"} <= set(body)
    assert body["time_seconds"] >= 0


def test_build_detail_marks_correctness_and_time():
    qs = get_bank()[:2]
    ids = [q.id for q in qs]
    answers = {qs[0].id: qs[0].answer, qs[1].id: (qs[1].answer + 1) % len(qs[1].options)}
    times = {qs[0].id: 12, qs[1].id: 30}
    d = build_detail(ids, answers, times)
    assert d[0]["is_correct"] is True and d[0]["time_seconds"] == 12
    assert d[1]["is_correct"] is False and d[1]["chosen_text"] != d[1]["correct_text"]


def test_submit_returns_per_question_detail(client):
    jid = _make_job()
    test = client.get(f"/iq-test?job_id={jid}").json()
    answers = {q["id"]: 0 for q in test["questions"]}
    times = {q["id"]: 7 for q in test["questions"]}
    body = client.post(
        "/iq-test/submit", json={"test_token": test["test_token"], "answers": answers, "times": times}
    ).json()
    assert len(body["detail"]) == test["total"]
    q0 = body["detail"][0]
    assert {"prompt", "options", "chosen", "correct", "is_correct", "time_seconds"} <= set(q0)
    assert q0["time_seconds"] == 7


def test_upload_stores_iq_details(client):
    jid = _make_job()
    qs = get_bank()[:3]
    detail = build_detail([q.id for q in qs], {q.id: q.answer for q in qs}, {q.id: 5 for q in qs})
    token = mint_result_token(jid, 3, 3, 100.0, time_seconds=15, detail=detail, ttl_seconds=3600)
    r = _upload(client, jid, iq_token=token)
    assert r.status_code == 200, r.text
    cand = _candidate(r.json()["id"])
    import json as _json
    stored = _json.loads(cand.iq_details)
    assert len(stored) == 3 and stored[0]["is_correct"] is True


def test_slower_attempt_scores_lower(client):
    # Same correct answers, but the slower attempt (issued 300s ago) scores lower.
    qs = get_bank()[:5]
    ids = [q.id for q in qs]
    answers = {q.id: q.answer for q in qs}
    now = int(time.time())
    fast = mint_test_token(1, ids, ttl_seconds=600, now=now)
    slow = mint_test_token(1, ids, ttl_seconds=600, now=now - 300)  # ~half the limit elapsed
    rf = client.post("/iq-test/submit", json={"test_token": fast, "answers": answers}).json()
    rs = client.post("/iq-test/submit", json={"test_token": slow, "answers": answers}).json()
    assert rf["accuracy"] == rs["accuracy"] == 100.0  # identical correctness
    assert rs["score"] < rf["score"]                  # but speed lowers the slow one
    assert rs["time_seconds"] > rf["time_seconds"]


def test_upload_attaches_time_and_attempted_at(client):
    jid = _make_job()
    token = mint_result_token(jid, 8, 10, 72.0, time_seconds=300, ttl_seconds=3600)
    r = _upload(client, jid, iq_token=token)
    assert r.status_code == 200, r.text
    cand = _candidate(r.json()["id"])
    assert cand.iq_score == 72.0 and cand.iq_time_seconds == 300
    assert cand.iq_attempted_at is not None


def test_submit_rejects_oversized_answers(client):
    answers = {f"q{i}": 0 for i in range(101)}  # over the 100 cap
    r = client.post("/iq-test/submit", json={"test_token": "x", "answers": answers})
    assert r.status_code == 422  # rejected by schema before scoring


def test_submit_rejects_out_of_range_index(client):
    r = client.post("/iq-test/submit", json={"test_token": "x", "answers": {"a": 999}})
    assert r.status_code == 422


def test_upload_attaches_iq_score(client):
    jid = _make_job()
    token = mint_result_token(jid, 8, 10, 80.0, ttl_seconds=3600)
    r = _upload(client, jid, iq_token=token)
    assert r.status_code == 200, r.text
    cand = _candidate(r.json()["id"])
    assert cand.iq_score == 80.0 and cand.iq_correct == 8 and cand.iq_total == 10


def test_upload_iq_token_is_single_use(client):
    # The same signed result token must not attach its score to a 2nd upload (replay).
    jid = _make_job()
    token = mint_result_token(jid, 8, 10, 80.0, ttl_seconds=3600)
    r1 = _upload(client, jid, iq_token=token)
    assert r1.status_code == 200, r1.text
    assert _candidate(r1.json()["id"]).iq_score == 80.0  # first use attaches
    r2 = _upload(client, jid, iq_token=token)            # replay same token
    assert r2.status_code == 200, r2.text
    assert _candidate(r2.json()["id"]).iq_score is None   # replay ignored


def test_upload_without_token_still_succeeds(client):
    jid = _make_job()
    r = _upload(client, jid)
    assert r.status_code == 200, r.text
    cand = _candidate(r.json()["id"])
    assert cand.iq_score is None  # recorded-only: absent token never blocks


def test_upload_ignores_token_for_other_job(client):
    jid = _make_job()
    other = mint_result_token(jid + 5000, 10, 10, 100.0, ttl_seconds=3600)
    r = _upload(client, jid, iq_token=other)
    assert r.status_code == 200, r.text  # still applies...
    assert _candidate(r.json()["id"]).iq_score is None  # ...but the mismatched score is ignored


def test_upload_ignores_invalid_token(client):
    jid = _make_job()
    r = _upload(client, jid, iq_token="garbage.token.value")
    assert r.status_code == 200, r.text
    assert _candidate(r.json()["id"]).iq_score is None
