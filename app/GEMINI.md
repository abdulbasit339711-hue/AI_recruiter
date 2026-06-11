# AI-Recruiter — Backend (FastAPI)

Scope: this file documents the `app/` package — the FastAPI REST API and the 3-tier
candidate scoring engine. For the whole-repo overview see the root `CLAUDE.md`.

## Run

```bash
# from the repo ROOT (so the `app` package resolves)
pip install -r requirements.txt
python -m spacy download en_core_web_sm      # Tier-1 parser model
uvicorn app.main:app --reload                # http://127.0.0.1:8000  (OpenAPI docs at /docs)
```

Run manual/dev scripts and tests from the repo root too:

```bash
python scripts/test_scoring.py     # seed the DB with sample candidates
pytest tests/                      # backend test suite
```

## Layout (`app/`)

- `main.py` — all FastAPI routes (job CRUD, upload, candidate ops, SSE, email/invite). Large; route surface listed below.
- `models.py` — SQLAlchemy ORM: `Job` and `Candidate` tables. Jobs are soft-deleted via `status` (Active/Archived) to preserve candidate history.
- `schemas.py` — Pydantic request/response models.
- `database.py` — engine/session + `run_migrations`. SQLite by default, PostgreSQL via `DATABASE_URL`.
- `config.yaml` — scoring weights, thresholds, LLM model, logging. Loaded at startup; **tune scoring here, not in code.**
- `scoring/` — the 3-tier engine:
  - `tier1.py` — profile rules via spaCy (email/phone/education/experience/skills).
  - `tier2.py` — semantic similarity via sentence-transformers.
  - `engine.py` — orchestrates the pipeline; `heuristics.py` has helpers.
- `llm/` — `groq_client.py` (Groq `llama-3.3-70b-versatile`, wrapped in a circuit breaker + fallback simulator), `json_parser.py`, `name_extractor.py`. Tier-3 LLM evaluation lives here.
- `intake/upload.py` — PDF resume ingest (pdfplumber text extraction).
- `queue/worker.py` — background scoring jobs.
- `events/` — Server-Sent Events: `broadcaster.py` (in-process pub/sub) + `sse.py`. Powers live score updates to the dashboard.
- `services/` — `email.py` (SMTP), `interview_invite.py`.
- `core/` — `auth.py` (admin bearer token), `circuit_breaker.py`, `ratelimit.py`, `model_registry.py`, `jd_embedding_cache.py`, `logging_config.py`, `status.py`.
- `scripts/migrate_sqlite_to_pg.py` — one-off SQLite→Postgres migration.
- `dashboard/app.py` — optional standalone Streamlit dashboard.

## Scoring pipeline

1. Resume PDF uploaded → `intake/upload.py` extracts text (pdfplumber).
2. Tier 1 (spaCy profile rules) + Tier 2 (semantic similarity) score.
3. **Tier 3 is gated:** the Groq LLM evaluation (with the job's custom prompt) runs only when `tier1 + tier2 ≥ pipeline.tier3_combined_threshold` (config.yaml, default 25).
4. Weighted final score is written to `candidates` (FK `job_id`). All weights/thresholds live in `config.yaml`.

## Key endpoints (see `main.py`)

- Jobs: `POST/GET /jobs`, `GET/PUT/PATCH/DELETE /jobs/{job_id}`
- Candidates: `POST /upload`, `GET /jobs/{job_id}/candidates`, `GET /candidates/{id}`, `GET /candidates/{id}/resume`, `PATCH /candidates/{id}/status`, `POST /candidates/{id}/notes`, `PATCH /candidates/{id}/score-override`, `GET /candidates/{id}/timeline`
- Live updates (SSE): `GET /jobs/{job_id}/events`, `GET /candidates/{id}/events`
- Reprocess: `POST /candidates/{id}/reprocess`, `POST /jobs/{job_id}/reprocess`
- Interview: `GET /candidates/{id}/interview`, `GET /candidates/{id}/interview-audio`, `POST /candidates/{id}/interview-invite`
- Ops: `GET /health`, `GET /metrics`, `POST /jobs/{job_id}/email`

## Conventions

- Admin endpoints require a bearer token (`core/auth.py`); the frontend proxy injects it. Backend `ADMIN_API_TOKEN` **must equal** the frontend's `ADMIN_API_TOKEN`.
- Groq calls degrade gracefully: on repeated failure the circuit breaker opens and a fallback simulator returns a Tier-3 estimate.

## Environment

```
GROQ_API_KEY=...            # Tier-3 LLM
DATABASE_URL=...            # optional; defaults to sqlite:///ai_recruiter.db
ADMIN_API_TOKEN=...         # must match the frontend proxy's token
```


---
_This file mirrors `CLAUDE.md` in this directory. The three agent guides (`CLAUDE.md`, `GEMINI.md`, `ANTIGRAVITY.md`) are kept identical — update all three together._
