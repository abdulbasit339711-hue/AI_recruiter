# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-Recruiter is a multi-tier automated recruitment system with:
- **FastAPI backend** for API endpoints and scoring engine
- **Next.js 15 frontend** for HR admin dashboard
- **Pipecat voice agent** for real-time candidate interviews
- **SQLite (default) / PostgreSQL** database with jobs and candidates tables
- **3-Tier Scoring Engine** (Profile Rules, Semantic Similarity, LLM Evaluation)

> **Per-component guides:** each subproject has its own agent guide (mirrored as `GEMINI.md` / `ANTIGRAVITY.md`):
> [`app/CLAUDE.md`](app/CLAUDE.md) (backend), [`frontend/CLAUDE.md`](frontend/CLAUDE.md), [`pipecat-quickstart/server/CLAUDE.md`](pipecat-quickstart/server/CLAUDE.md) (voice bot).

## Architecture

```
            HR Administrator
                  │  Next.js dashboard → same-origin /api/admin proxy (injects admin token)
                  ▼
           FastAPI backend  (:8000)
        ┌─────────┴─────────┐
        ▼                   ▼
    jobs table         candidates table
  (JDs & prompts)     (scores & job_id FK)
        │                   ▲
        └─── 3-Tier Scoring Pipeline ───┐  (writes scores back)
             Tier 1  Profile rules        (spaCy, /30)
             Tier 2  Semantic similarity  (sentence-transformers, /40)
             Tier 3  LLM evaluation       (Groq, gated, /30)
                  │
                  ▼
         Pipecat voice interview bot  (:7860)
       real-time STT → LLM → TTS screening over WebRTC/LiveKit
```

## Essential Commands

### Backend (FastAPI)
```bash
# Setup
cd app
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows
pip install -r ../requirements.txt

# Development
uvicorn app.main:app --reload  # API runs on http://127.0.0.1:8000

# Testing
python scripts/test_scoring.py       # Test scoring engine
python scripts/test_hr_endpoints.py  # Test HR endpoints
pytest tests/                        # Run all backend tests
```

### Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev    # Runs on http://localhost:3000
npm run build  # Production build
npm run lint   # ESLint check
```

### Voice Agent (Pipecat)
```bash
cd pipecat-quickstart/server
uv sync                        # Install dependencies
cp .env.example .env          # Configure API keys
uv run runner.py              # Interview server on :7860 (use THIS to run the voice service)
pytest                        # Run voice agent tests
```

**Important:** `runner.py` is the interview HTTP server — it owns `/interview/validate`,
`/events`, `/chat`, and `/token`, and spawns a `bot.py` worker per interview. Run
`runner.py`, not `bot.py`. Starting `bot.py` directly binds :7860 with only the Pipecat
WebRTC server, which lacks `/interview/validate`, so every interview link 404s.

### Database

SQLite by default (`ai_recruiter.db`); override with `DATABASE_URL` for PostgreSQL.
Jobs use soft-delete (`status` = Active/Archived) to preserve candidate history.

- **`jobs`** — `id`, `title`, `department`, `job_description`, `llm_prompt` (custom Tier-3 prompt), `status`, `created_at`
- **`candidates`** — `id`, `filename`, `email`, `raw_text`, `job_id` (FK → `jobs.id`), `tier1` (/30), `tier2` (/40), `tier3` (/30), `total_score` (/100), `summary`, `evidence` (JSON), `status` (Pending/Processed/Failed), `created_at`

## Architecture & Key Components

### Backend Structure (app/)
- **main.py**: FastAPI routes for job CRUD, candidate upload, scoring
- **scoring/**: 3-tier scoring engine implementation
  - Tier 1: Profile rules (spaCy parsing) - 30 points
  - Tier 2: Semantic similarity (sentence-transformers) - 40 points
  - Tier 3: LLM evaluation (Groq/fallback) - 30 points
- **llm/**: Groq API integration with fallback simulator
- **database.py**: SQLAlchemy models and connection
- **config.yaml**: Scoring weights configuration

### Frontend Structure (frontend/src/)
- **app/**: Next.js 15 App Router pages
- **components/admin/**: Dashboard components (JobCard, CandidateList, ScoreVisualization)
- **hooks/**: API integration with React Query and Zustand state management
- **lib/**: Utilities including CSV export functionality

### Voice Agent (pipecat-quickstart/server/)
- **runner.py**: Interview HTTP server (run this) — routes `/interview/validate`, `/events`, `/chat`, `/token`; spawns a bot worker per interview
- **bot.py**: Per-interview bot worker with STT→LLM→TTS pipeline (launched by runner.py, not run directly)
- **question_flow_processor.py**: Interview state machine
- **transcript_accumulator.py**: Conversation tracking
- Uses Deepgram (STT), OpenAI (LLM), Cartesia (TTS)

## Critical Implementation Details

### Scoring Engine Flow
1. PDF resumes uploaded via the `/upload` endpoint
2. Text extraction with pdfplumber
3. Profile validation (Tier 1) using spaCy
4. Semantic matching (Tier 2) with sentence-transformers
5. LLM evaluation (Tier 3) via Groq API
6. Scores stored in candidates table with job_id foreign key

### Job Management
- Jobs have soft-delete: status='Archived' preserves candidate history
- Each job has custom LLM prompt for Tier 3 evaluation
- Frontend fetches active jobs via `/jobs` endpoint

### Voice Interview Integration
- Pipecat bot reads candidate scores from database
- Conducts structured interviews based on job description
- Real-time WebRTC/LiveKit audio streaming
- Interview transcripts stored for review

## Environment Variables

Required in `.env`:
```
GROQ_API_KEY=your_groq_api_key
OPENAI_API_KEY=your_openai_key      # For Pipecat
DEEPGRAM_API_KEY=your_deepgram_key  # For Pipecat
CARTESIA_API_KEY=your_cartesia_key  # For Pipecat
```

## Testing Strategy

- **Backend**: Unit tests for scoring tiers, integration tests for API endpoints
- **Frontend**: Component tests, E2E with Playwright
- **Voice Agent**: Mock interview sessions, question flow validation
- Run `pytest` in respective directories for automated testing

## Key API Endpoints

(See `app/main.py` for the full surface.)

- `POST /jobs` / `GET /jobs`: Create / list jobs
- `GET|PUT|PATCH|DELETE /jobs/{job_id}`: Retrieve / update / soft-archive a job
- `POST /upload`: Process a candidate resume (links to a `job_id`)
- `GET /jobs/{job_id}/candidates`: Ranked candidates for a job
- `GET /candidates/{id}`: Candidate detail; `PATCH /candidates/{id}/status`, `/score-override`; `POST /candidates/{id}/notes`
- `GET /jobs/{job_id}/events`, `GET /candidates/{id}/events`: Server-Sent Events (live score updates)
- `POST /candidates/{id}/interview-invite`, `GET /candidates/{id}/interview`: Voice interview lifecycle

---
_This file mirrors `CLAUDE.md` in this directory. The three agent guides (`CLAUDE.md`, `GEMINI.md`, `ANTIGRAVITY.md`) are kept identical — update all three together._
