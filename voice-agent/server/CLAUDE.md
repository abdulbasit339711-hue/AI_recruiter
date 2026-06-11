# AI-Recruiter — Voice Bot (Pipecat)

Scope: documents `voice-agent/server/` — the real-time voice interview agent.
Whole-repo overview is in the root `CLAUDE.md`.

## ⚠️ Run `runner.py`, not `bot.py`

```bash
cd voice-agent/server
uv sync
cp .env.example .env            # fill in API keys + DB connection
uv run runner.py                # interview HTTP server on :7860
```

`runner.py` is the interview HTTP server — it owns `/interview/validate`, `/events`,
`/chat`, and `/token`, and **spawns a `bot.py` worker per interview**. Starting `bot.py`
directly binds :7860 with only the Pipecat WebRTC server (no `/interview/validate`), so
every interview link 404s. Requires Python ≥ 3.11.

## Pipeline

Deepgram (STT) → LLM → Cartesia (TTS), streamed over WebRTC/LiveKit. A dual-LLM setup
(`bot_manager.py` + `processors/judge_processor.py`) runs a primary conversational
model alongside a judge/scoring model.

## Layout

- `runner.py` — interview HTTP server + per-interview worker spawner (**the entrypoint**).
- `bot.py` — per-interview pipeline worker (launched by `runner.py`, not run directly).
- `bot_manager.py` — dual-LLM orchestration.
- `session_factory.py`, `interview_session.py` — session lifecycle + domain model.
- `database.py` — `DatabaseConfig` / `db_manager` (PostgreSQL).
- `processors/` — Pipecat `FrameProcessor`s:
  - `question_flow_processor.py` — interview state machine.
  - `transcript_accumulator.py` — conversation tracking.
  - `goal_tracking_processor.py` + `adaptive_questioning_processor.py` — goal-driven adaptive follow-ups.
  - `judge_processor.py` — dual-LLM scoring/judging.
  - `resilient_tts.py` — TTS with failover; `transcript_metrics_processors.py` — transcript/metrics helpers.
- `services/` — `goal_tracking_service.py`, `role_config_service.py`.
- `events/broadcaster.py` — SSE pub/sub for the dashboard. `core/metrics.py`. `llm/json_parser.py`.
- `alembic/` + `scripts/bootstrap_db.py` — schema migrations / first-run bootstrap.
- `tests/` — pytest suite (`pyproject.toml` sets `testpaths=["tests"]`, `pythonpath=["."]`); `tests/test_conversations/` holds replay fixtures.

## Database & sessions

- PostgreSQL via SQLAlchemy (`DatabaseConfig` / `db_manager`); migrate with Alembic, bootstrap a fresh DB with `scripts/bootstrap_db.py`.
- **session_id convention:** child tables link to the parent by an external `VARCHAR` `session_id`, not the UUID primary key.
- **Resume-on-restart:** re-opening an interview link resumes the *same* session; the DB session status (`resumed` flag) is authoritative.
- Post-call analysis + session finalization persist scores and broadcast over SSE.

### Shared-Postgres contract with the backend (IMPORTANT)

The voice agent and the FastAPI backend (`app/`) share **one Postgres** (same `DATABASE_URL` /
`DB_*`). The split of ownership is:

- **Voice agent OWNS / writes:** `interview_sessions`, `session_transcripts`, `session_goals`,
  `session_metrics`, `goal_progress_events`, `goal_templates`.
- **Backend OWNS / writes:** `jobs`, `candidates`.
- **Backend READS the voice tables directly** to show interview results in the HR panel —
  see `app/main.py::get_candidate_interview` (~L691) and `get_candidate_interview_audio`,
  which `SELECT … FROM interview_sessions/session_transcripts/session_goals/session_metrics`.

Linkage: `interview_sessions.candidate_id` → `candidates.id` (FK); child rows link to the
session by the **VARCHAR `session_id`** (not the UUID PK). This is an implicit cross-service
contract: changing the voice schema of those tables (column names/shapes) will break the
backend's interview endpoints, and vice-versa. Treat those columns as a shared interface.

## When something breaks

Check `ERRORS_AND_SOLUTIONS.md` first — it's the running errors-and-fixes runbook for
this service (recurring STT/TTS/LLM/DB issues and their resolutions). See also
`GOAL_TRACKING.md` and `POST_CALL_ANALYSIS.md`.

## Tests

```bash
uv run pytest          # collects from tests/
```

## Environment (`.env`)

```
OPENAI_API_KEY=...      # LLM
DEEPGRAM_API_KEY=...    # STT
CARTESIA_API_KEY=...    # TTS
GROQ_API_KEY=...        # judge / scoring LLM
# + PostgreSQL connection vars (see .env.example)
```
