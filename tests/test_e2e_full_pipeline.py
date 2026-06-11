"""End-to-end recruitment pipeline test.

Walks one candidate through the entire system, end to end:

    1. Create a job              -> POST /jobs            (real HTTP API)
    2. Apply / upload a resume   -> POST /upload          (real HTTP API)
    3. Score the resume          -> evaluate_candidate_pipeline (Tier 1/2/3)
    4. Conduct a CHAT interview  -> seeded interview_sessions row (no audio)
    5. Conduct an AUDIO interview-> seeded interview_sessions row (with audio)
    6. Read combined results     -> GET /candidates/{id}/interview (real HTTP API)

The recruiter backend is exercised through FastAPI's TestClient. The voice-agent
interview rows (interview_sessions / session_transcripts / session_goals /
session_metrics) are written directly because they are normally produced by the
pipecat server, which exposes no HTTP "create interview" endpoint we can drive
from a test. Those tables live in the SAME database as the recruiter backend.

External scoring services (spaCy, sentence-transformers, Groq) are mocked, so the
run is deterministic and works fully offline.

The interview tables only exist on PostgreSQL deployments. When the configured
DATABASE_URL has no interview_sessions table (e.g. a SQLite CI box), the interview
portion is skipped instead of failing.

Run it:
    pytest tests/test_e2e_full_pipeline.py -v -s
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import status as S
from app.database import SessionLocal
from app.main import app
from app.models import Candidate, Job
from app.scoring.engine import evaluate_candidate_pipeline


RESUME_TEXT = """
Jane Smith
jane@example.com | 555-123-4567

Experience
Senior Python Engineer at TechCorp (5 years) building FastAPI services,
PostgreSQL data layers, and Dockerized microservices on AWS.

Education
BS Computer Science

Skills
Python, FastAPI, SQL, PostgreSQL, Docker, AWS
"""

ROLE_TYPE = "backend_engineer"  # matches seeded goal_templates


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _interview_tables_exist(db) -> bool:
    """True if the voice-agent tables are present (PostgreSQL deployments)."""
    try:
        db.execute(text("SELECT 1 FROM interview_sessions LIMIT 1"))
        db.execute(text("SELECT 1 FROM goal_templates LIMIT 1"))
        return True
    except Exception:
        db.rollback()
        return False


def _mock_scoring(monkeypatch) -> None:
    """Make Tier 1/2/3 deterministic and offline (no spaCy / embeddings / Groq)."""
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
            "summary": "Strong backend candidate with relevant Python/FastAPI/SQL experience.",
            "evidence": ["Built FastAPI services.", "Worked with PostgreSQL systems."],
        },
    )


def _goal_template_ids(db, n: int = 3) -> list:
    rows = db.execute(
        text(
            "SELECT id FROM goal_templates WHERE role_type = :rt "
            "ORDER BY priority_weight DESC LIMIT :n"
        ),
        {"rt": ROLE_TYPE, "n": n},
    ).scalars().all()
    return list(rows)


def _seed_interview(
    db,
    *,
    candidate_id: int,
    job_id: int,
    audio_path,
    pipeline_mode: str,
    transcript: list,
    goal_template_ids: list,
    assessment: str,
    created_at: datetime,
) -> str:
    """Insert one finalized interview (session + transcript + goals + metrics).

    Mirrors what the pipecat server writes when an interview ends. Returns the
    external session_id. `audio_path=None` => chat interview; a path => audio.
    """
    session_id = str(uuid4())
    started = created_at
    ended = created_at + timedelta(minutes=12)

    db.execute(
        text(
            """
            INSERT INTO interview_sessions
                (session_id, candidate_id, job_id, candidate_name, role_type,
                 company_name, status, pipeline_mode, started_at, ended_at,
                 duration_seconds, overall_assessment, audio_path, created_at)
            VALUES
                (:sid, :cid, :jid, :cname, :rt, :co, 'completed', :mode,
                 :start, :end, :dur, :assess, :audio, :created)
            """
        ),
        {
            "sid": session_id,
            "cid": candidate_id,
            "jid": job_id,
            "cname": "Jane Smith",
            "rt": ROLE_TYPE,
            "co": "ACME Corp",
            "mode": pipeline_mode,
            "start": started,
            "end": ended,
            "dur": 720,
            "assess": assessment,
            "audio": audio_path,
            "created": created_at,
        },
    )

    for seq, (speaker, line, tokens) in enumerate(transcript, start=1):
        evaluation = None
        if speaker == "candidate":
            evaluation = json.dumps(
                {"score": 8, "depth": "medium", "strengths": ["concrete example"], "weaknesses": []}
            )
        db.execute(
            text(
                """
                INSERT INTO session_transcripts
                    (session_id, speaker, text, timestamp, sequence_number,
                     tokens_estimated, evaluation)
                VALUES
                    (:sid, :sp, :tx, :ts, :seq, :tok, CAST(:ev AS jsonb))
                """
            ),
            {
                "sid": session_id,
                "sp": speaker,
                "tx": line,
                "ts": started + timedelta(seconds=seq * 20),
                "seq": seq,
                "tok": tokens,
                "ev": evaluation,
            },
        )

    for tmpl_id in goal_template_ids:
        db.execute(
            text(
                """
                INSERT INTO session_goals
                    (session_id, goal_template_id, completion_status,
                     progress_score, confidence_level)
                VALUES
                    (:sid, :tid, 'completed', 0.85, 0.80)
                """
            ),
            {"sid": session_id, "tid": tmpl_id},
        )

    metric_rows = [
        ("llm_input", "groq", "llama-3.3-70b-versatile", 1200, 0.000180),
        ("llm_output", "groq", "llama-3.3-70b-versatile", 400, 0.000240),
        ("tts_tokens", "cartesia", "sonic", 350, 0.0),
    ]
    for mtype, svc, model, tok, cost in metric_rows:
        db.execute(
            text(
                """
                INSERT INTO session_metrics
                    (session_id, metric_type, service_name, model_name,
                     token_count, cost_usd)
                VALUES (:sid, :mt, :svc, :model, :tok, :cost)
                """
            ),
            {"sid": session_id, "mt": mtype, "svc": svc, "model": model, "tok": tok, "cost": cost},
        )

    db.commit()
    return session_id


def _cleanup(job_id, candidate_id, session_ids) -> None:
    db = SessionLocal()
    try:
        for sid in session_ids:
            # ON DELETE CASCADE clears transcripts/goals/metrics.
            db.execute(text("DELETE FROM interview_sessions WHERE session_id = :s"), {"s": sid})
        if candidate_id is not None:
            db.query(Candidate).filter(Candidate.id == candidate_id).delete()
        if job_id is not None:
            db.query(Job).filter(Job.id == job_id).delete()
        db.commit()
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# The pipeline test
# --------------------------------------------------------------------------- #
def test_full_recruitment_pipeline(monkeypatch, capsys):
    _mock_scoring(monkeypatch)
    monkeypatch.setattr("app.main.validate_and_extract", lambda *_a: RESUME_TEXT)
    monkeypatch.setattr("app.main.enqueue_candidate", lambda _cid: None)  # score synchronously below
    monkeypatch.setenv("ADMIN_API_TOKEN", "test-token")
    auth = {"Authorization": "Bearer test-token"}

    client = TestClient(app)
    job_id = candidate_id = None
    session_ids: list[str] = []

    def log(msg: str) -> None:
        with capsys.disabled():
            print(msg)

    try:
        # --- 1. Create a job --------------------------------------------------
        resp = client.post(
            "/jobs",
            params={
                "title": "Senior Python Developer",
                "department": "Engineering",
                "job_description": "Python FastAPI SQL AWS Docker PostgreSQL",
            },
            headers=auth,
        )
        assert resp.status_code == 200, resp.text
        job_id = resp.json()["id"]
        log(f"[1] job created            id={job_id}")

        # Tag the role so seeded interview goals line up with goal_templates.
        db = SessionLocal()
        try:
            db.query(Job).filter(Job.id == job_id).update({"role_type": ROLE_TYPE})
            db.commit()
        finally:
            db.close()

        # --- 2. Applicant uploads a resume -----------------------------------
        resp = client.post(
            "/upload",
            params={"job_id": job_id},
            files={"file": ("resume.pdf", b"fake pdf bytes", "application/pdf")},
        )
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        candidate_id = payload["id"]
        assert payload["status"] == S.QUEUED
        assert payload["job_id"] == job_id
        # Upload must NOT hand back an interview link: invites are minted only when HR
        # explicitly triggers them after review, never self-service from the apply flow.
        assert "interview_token" not in payload
        log(f"[2] applicant uploaded     id={candidate_id} status={payload['status']}")

        # --- 3. Resume evaluation (Tier 1 + Tier 2 + Tier 3) ------------------
        db = SessionLocal()
        try:
            scored = evaluate_candidate_pipeline(candidate_id, db)
            assert scored.tier1 == 20.0
            assert scored.tier2 == 20.0
            assert scored.tier3 == 45.0
            assert scored.total_score == 85.0
            assert scored.status == S.SHORTLISTED
            assert scored.name == "Jane Smith"
            log(
                f"[3] resume evaluated       t1={scored.tier1} t2={scored.tier2} "
                f"t3={scored.tier3} total={scored.total_score} -> {scored.status}"
            )
            interview_capable = _interview_tables_exist(db)
        finally:
            db.close()

        # The resume-scoring half of the pipeline is fully verified above.
        if not interview_capable:
            pytest.skip(
                "interview_sessions table not found (SQLite?) — "
                "resume-scoring half verified; skipping chat/audio interview half."
            )

        # --- 4 & 5. Chat interview, then audio interview ---------------------
        db = SessionLocal()
        try:
            goal_ids = _goal_template_ids(db, n=3)
            assert goal_ids, f"no goal_templates seeded for role_type={ROLE_TYPE}"
            now = datetime.utcnow()

            chat_sid = _seed_interview(
                db,
                candidate_id=candidate_id,
                job_id=job_id,
                audio_path=None,
                pipeline_mode="single",
                transcript=[
                    ("agent", "Welcome! Tell me about a backend system you designed.", 12),
                    ("candidate", "I built a FastAPI service backed by PostgreSQL with Redis caching "
                                  "to handle bursty traffic, sharding the hot tables.", 28),
                    ("agent", "How did you handle schema migrations safely?", 10),
                    ("candidate", "Additive, backward-compatible migrations rolled out before code, "
                                  "with a feature flag to switch reads over.", 24),
                ],
                goal_template_ids=goal_ids,
                assessment="Chat screen: solid system-design fundamentals, clear communicator.",
                created_at=now - timedelta(hours=1),  # older -> not the 'latest'
            )
            session_ids.append(chat_sid)
            log(f"[4] chat interview seeded  session={chat_sid[:8]} (no audio)")

            audio_sid = _seed_interview(
                db,
                candidate_id=candidate_id,
                job_id=job_id,
                audio_path="/tmp/ai_recruiter_test_interview.wav",
                pipeline_mode="dual",
                transcript=[
                    ("agent", "Walk me through optimizing a slow query in production.", 11),
                    ("candidate", "I profiled with EXPLAIN ANALYZE, found a missing composite index, "
                                  "added it, and cut p95 latency from 800ms to 40ms.", 31),
                    ("agent", "Great. How do you decide SQL vs NoSQL?", 9),
                    ("candidate", "Relational by default for integrity; NoSQL when access patterns "
                                  "are key-value or write-heavy and denormalized.", 22),
                ],
                goal_template_ids=goal_ids,
                assessment="Audio interview: strong DB optimization, pragmatic trade-off reasoning.",
                created_at=now,  # newest -> what the endpoint returns
            )
            session_ids.append(audio_sid)
            log(f"[5] audio interview seeded session={audio_sid[:8]} (audio_path set)")

            # Both interviews are persisted, distinguished by audio_path.
            chat_audio = db.execute(
                text("SELECT audio_path FROM interview_sessions WHERE session_id = :s"),
                {"s": chat_sid},
            ).scalar()
            assert chat_audio is None
        finally:
            db.close()

        # --- 6. Combined results via the public API endpoint -----------------
        resp = client.get(f"/candidates/{candidate_id}/interview", headers=auth)
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # Endpoint returns the most recent session -> the audio interview.
        assert data["has_interview"] is True
        assert data["has_audio"] is True
        assert data["session"]["session_id"] == audio_sid
        assert data["session"]["status"] == "completed"
        assert data["session"]["role_type"] == ROLE_TYPE

        # Transcript came through with both speakers.
        speakers = {t["speaker"] for t in data["transcript"]}
        assert {"agent", "candidate"} <= speakers
        assert len(data["transcript"]) == 4

        # Goals resolved against goal_templates and report progress.
        assert len(data["goals"]) == 3
        assert all(g["completion_status"] == "completed" for g in data["goals"])

        # Metrics: interview token usage + resume-scoring (Tier 3) cost.
        im = data["metrics"]["interview"]
        assert im["llm_input_tokens"] == 1200
        assert im["llm_output_tokens"] == 400
        assert im["tts_tokens"] == 350
        assert im["stt_tokens"] > 0          # summed from candidate transcript tokens
        assert im["total_tokens"] == im["stt_tokens"] + 1200 + 400 + 350
        assert im["cost_usd"] > 0
        assert "scoring" in data["metrics"]

        log(
            f"[6] results fetched        audio={data['has_audio']} "
            f"turns={len(data['transcript'])} goals={len(data['goals'])} "
            f"interview_tokens={im['total_tokens']}"
        )
        log("[OK] full pipeline: job -> applicant -> evaluation -> chat -> audio -> results")

    finally:
        _cleanup(job_id, candidate_id, session_ids)
