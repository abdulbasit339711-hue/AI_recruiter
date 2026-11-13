"""GET /candidates/{id}/score-explanation — the HR 'why this score' payload."""

import json

import pytest

pytest.importorskip("pdfplumber")  # the candidates router imports the PDF intake module

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.utils import _utcnow
from app.database import SessionLocal
from app.models import Candidate, Job
from app.routers import candidates


@pytest.fixture
def world():
    db = SessionLocal()
    now = _utcnow().isoformat()
    job = Job(title="j", department="d", job_description="x", created_at=now, tier3_weight=1.5)
    db.add(job); db.commit()
    skipped = Candidate(filename="a", job_id=job.id, tier1=20, tier2=3, tier3=0, total_score=23,
                        status="Ungraded", created_at=now, warnings=json.dumps(["thin résumé"]))
    fallback = Candidate(filename="b", job_id=job.id, tier1=25, tier2=35, tier3=22, total_score=82,
                         status="Shortlisted", created_at=now, evaluation_data=json.dumps({"is_fallback": True}))
    db.add_all([skipped, fallback]); db.commit()
    api = FastAPI(); api.include_router(candidates.router)
    yield TestClient(api), skipped.id, fallback.id
    db.close()


def test_skipped_tier3_is_explained(world):
    c, sid, _ = world
    r = c.get(f"/candidates/{sid}/score-explanation").json()
    t3 = r["tiers"][2]
    assert t3["skipped"] and "not run" in t3["note"] and t3["weight"] == 1.5
    assert r["warnings"] == ["thin résumé"]


def test_fallback_flagged_and_outcome_threshold(world):
    c, _, fid = world
    r = c.get(f"/candidates/{fid}/score-explanation").json()
    assert r["tiers"][2]["fallback"] and "low confidence" in r["tiers"][2]["note"]
    assert "shortlist threshold" in r["outcome"]


def test_unknown_candidate_404(world):
    assert world[0].get("/candidates/999999/score-explanation").status_code == 404
