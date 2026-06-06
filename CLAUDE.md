# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-Recruiter is a multi-tier automated recruitment system with:
- **FastAPI backend** for API endpoints and scoring engine
- **Next.js 15 frontend** for HR admin dashboard
- **Pipecat voice agent** for real-time candidate interviews
- **SQLite database** with jobs and candidates tables
- **3-Tier Scoring Engine** (Profile Rules, Semantic Similarity, LLM Evaluation)

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
python test_scoring.py         # Test scoring engine
python test_hr_endpoints.py    # Test HR endpoints
pytest tests/                  # Run all backend tests
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
uv run bot.py                 # WebRTC mode
uv run bot.py --transport livekit  # LiveKit mode
pytest                        # Run voice agent tests
```

### Database Operations
```bash
# SQLite database location: recruiter.db
# Schema includes: jobs, candidates tables
# Jobs have soft-delete via status field (Active/Archived)
```

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
- **bot.py**: Main bot implementation with STT→LLM→TTS pipeline
- **question_flow_processor.py**: Interview state machine
- **transcript_accumulator.py**: Conversation tracking
- Uses Deepgram (STT), OpenAI (LLM), Cartesia (TTS)

## Critical Implementation Details

### Scoring Engine Flow
1. PDF resumes uploaded via `/upload_resume` endpoint
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

- `POST /jobs`: Create new job opening
- `GET /jobs`: List active jobs
- `POST /upload_resume`: Process candidate resume
- `GET /candidates/{job_id}`: Get ranked candidates for job
- `DELETE /candidates/{id}`: Remove candidate
- `PUT /jobs/{id}`: Update job (including archival)