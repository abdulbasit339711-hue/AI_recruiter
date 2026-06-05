from datetime import datetime

from fastapi.testclient import TestClient

from app.core import status as S
from app.database import SessionLocal
from app.main import app
from app.models import Candidate, Job
from app.scoring.engine import evaluate_candidate_pipeline


RESUME_TEXT = """
Jane Smith
jane@example.com | 555-123-4567

Experience
Senior Python Engineer building FastAPI services and PostgreSQL systems.

Education
BS Computer Science

Skills
Python, FastAPI, SQL, PostgreSQL, Docker, AWS
"""


def _delete_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            db.delete(job)
            db.commit()
    finally:
        db.close()


def test_upload_returns_queued_and_resume_text_endpoint(monkeypatch):
    queued_ids: list[int] = []
    monkeypatch.setattr("app.main.validate_and_extract", lambda *_args: RESUME_TEXT)
    monkeypatch.setattr("app.main.enqueue_candidate", lambda candidate_id: queued_ids.append(candidate_id))

    client = TestClient(app)
    job_response = client.post(
        "/jobs",
        params={
            "title": "Senior Python Developer",
            "department": "Engineering",
            "job_description": "Python FastAPI SQL AWS Docker",
        },
    )
    assert job_response.status_code == 200
    job_id = job_response.json()["id"]

    try:
        upload_response = client.post(
            "/upload",
            params={"job_id": job_id},
            files={"file": ("resume.pdf", b"fake pdf bytes", "application/pdf")},
        )

        assert upload_response.status_code == 200
        payload = upload_response.json()
        assert payload["status"] == S.QUEUED
        assert payload["job_id"] == job_id
        assert queued_ids == [payload["id"]]

        resume_response = client.get(f"/candidates/{payload['id']}/resume")
        assert resume_response.status_code == 200
        assert "Jane Smith" in resume_response.text
        assert "FastAPI" in resume_response.text
    finally:
        _delete_job(job_id)


def test_queued_candidate_can_complete_pipeline_without_external_services(monkeypatch):
    monkeypatch.setattr(
        "app.scoring.engine.score_tier1",
        lambda _resume_text: {
            "tier1_total": 20.0,
            "name": "Jane Smith",
            "email": "jane@example.com",
            "phone": "555-123-4567",
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        "app.scoring.engine.score_tier2",
        lambda *_args, **_kwargs: {"tier2_score": 20.0, "warnings": []},
    )
    monkeypatch.setattr(
        "app.scoring.engine.evaluate_with_llm",
        lambda *_args, **_kwargs: {
            "name": "Jane Smith",
            "email": "jane@example.com",
            "phone": "555-123-4567",
            "companies": ["TechCorp"],
            "current_role": "Senior Python Engineer",
            "total_years_experience": 5,
            "education": {"degree": "BS Computer Science", "institution": "", "year": None},
            "skills_matched": ["Python", "FastAPI", "SQL"],
            "skills_missing": ["Kubernetes"],
            "tier3_score": 45.0,
            "status": S.REVIEWED,
            "summary": "Strong backend candidate with relevant Python, FastAPI, and SQL experience.",
            "evidence": ["Built FastAPI services.", "Worked with PostgreSQL systems."],
        },
    )

    db = SessionLocal()
    job = Job(
        title="Senior Python Developer",
        department="Engineering",
        job_description="Python FastAPI SQL AWS Docker",
        status="Active",
        created_at=datetime.utcnow().isoformat(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    candidate = Candidate(
        filename="resume.pdf",
        raw_text=RESUME_TEXT,
        job_id=job.id,
        status=S.QUEUED,
        created_at=datetime.utcnow().isoformat(),
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    candidate_id = candidate.id
    job_id = job.id

    try:
        evaluated = evaluate_candidate_pipeline(candidate_id, db)

        assert evaluated.status == S.SHORTLISTED
        assert evaluated.total_score == 85.0
        assert evaluated.tier1 == 20.0
        assert evaluated.tier2 == 20.0
        assert evaluated.tier3 == 45.0
        assert evaluated.name == "Jane Smith"
    finally:
        db.close()
        _delete_job(job_id)
