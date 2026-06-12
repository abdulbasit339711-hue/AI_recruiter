"""Throwaway end-to-end driver: real mock résumés through IQ -> upload -> scoring.

Exercises the REAL pipeline (pdfplumber extraction, spaCy Tier 1, sentence-transformers
Tier 2; Tier 3 falls back to the simulator when no GROQ key). Scoring is run
synchronously so results are deterministic to inspect. Not a pytest; run directly.
"""

import glob
import os

os.environ.pop("ADMIN_API_TOKEN", None)  # keep the public apply flow open

from fastapi.testclient import TestClient
from unittest.mock import patch

import app.main as m
from app.core.ratelimit import reset_rate_limits
from app.database import SessionLocal
from app.models import Candidate, Job
from app.scoring.engine import evaluate_candidate_pipeline

JOB = dict(
    title="Senior Backend Engineer",
    department="Engineering",
    job_description=(
        "We are hiring a Senior Backend Engineer with strong Python and FastAPI "
        "experience. Responsibilities include designing REST APIs, working with "
        "PostgreSQL and SQLAlchemy, building scalable microservices, Docker, and CI/CD. "
        "Required skills: Python, FastAPI, SQL, REST, Docker, testing, cloud."
    ),
)


def make_job() -> int:
    db = SessionLocal()
    try:
        j = Job(status="Active", created_at="2026-06-13T00:00:00", **JOB)
        db.add(j); db.commit(); db.refresh(j)
        return j.id
    finally:
        db.close()


def run_iq(client, job_id):
    r = client.get(f"/iq-test?job_id={job_id}")
    assert r.status_code == 200, r.text
    test = r.json()
    # Answer the first half correctly-ish: just submit index 0 for all (deterministic).
    answers = {q["id"]: 0 for q in test["questions"]}
    sub = client.post("/iq-test/submit", json={"test_token": test["test_token"], "answers": answers})
    assert sub.status_code == 200, sub.text
    s = sub.json()
    return s["result_token"], s


def upload_and_score(client, job_id, path, iq_token=None):
    fname = os.path.basename(path)
    with open(path, "rb") as fh:
        data = {"iq_token": iq_token} if iq_token else None
        r = client.post(
            "/upload",
            params={"job_id": job_id},
            files={"file": (fname, fh.read(), "application/pdf")},
            data=data,
        )
    if r.status_code != 200:
        return fname, r.status_code, r.json().get("detail", "")[:80], None
    cid = r.json()["id"]
    db = SessionLocal()
    try:
        scored = evaluate_candidate_pipeline(cid, db)  # synchronous, real Tier1/2/3
        cand = db.query(Candidate).filter(Candidate.id == cid).first()
        return fname, 200, scored, cand
    finally:
        db.close()


def main():
    with patch("app.main.enqueue_candidate", lambda _cid: None):
        client = TestClient(m.app)
        job_id = make_job()
        print(f"\n=== Job #{job_id}: {JOB['title']} ===")

        iq_token, iq = run_iq(client, job_id)
        print(f"IQ screen: {iq['correct']}/{iq['total']} = {iq['score']}%  (token attached to uploads)\n")

        print("--- GRADED RÉSUMÉS (real Tier1+Tier2, Tier3 fallback) ---")
        print(f"{'file':<26}{'T1':>5}{'T2':>6}{'T3':>6}{'total':>7}  {'status':<12}{'IQ':>5}")
        reset_rate_limits()  # batch driver from one IP — don't trip the per-IP upload limit
        for path in sorted(glob.glob("test_resumes/*.pdf")):
            reset_rate_limits()
            fname, code, scored, cand = upload_and_score(client, job_id, path, iq_token)
            if code != 200:
                print(f"{fname:<26}  -> {code} {scored}")
                continue
            print(f"{fname:<26}{scored.tier1:>5.1f}{scored.tier2:>6.1f}{scored.tier3:>6.1f}"
                  f"{scored.total_score:>7.1f}  {scored.status:<12}{(cand.iq_score or 0):>4.0f}%")

        print("\n--- EDGE CASES (expect graceful reject / flagging) ---")
        for path in sorted(glob.glob("edge_case_resumes/*.pdf")):
            reset_rate_limits()
            fname, code, scored, cand = upload_and_score(client, job_id, path)
            if code != 200:
                print(f"{fname:<28} -> HTTP {code}: {scored}")
            else:
                warn = (getattr(scored, "warnings", None) or "")[:40]
                print(f"{fname:<28} -> scored total={scored.total_score:.1f} status={scored.status} warn={warn}")


if __name__ == "__main__":
    main()
