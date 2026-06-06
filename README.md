# 💼 AI-Recruiter: Multi-Job Recruitment & Voice Interview System

AI-Recruiter is an end-to-end automated recruitment platform designed to ingest candidate resumes, score them using a multi-tier engine, and conduct real-time voice interviews.

## 🚀 Core Features

- **Multi-Job Management**: Create and manage multiple job openings, each with custom descriptions and evaluation prompts.
- **3-Tier Scoring Engine**:
    - **Tier 1 (Profile Rules)**: Automated parsing for contact info and key resume sections using spaCy.
    - **Tier 2 (Semantic Similarity)**: Vector-based comparison between resumes and JDs using Sentence-Transformers.
    - **Tier 3 (Qualitative LLM)**: Deep-dive evaluation and fit analysis powered by Groq (Llama 3).
- **Next.js 15 Frontend**: A modern, responsive dashboard for HR administrators to manage jobs, view candidate leaderboards, and deep-dive into scores.
- **Pipecat Voice Agent**: Real-time AI voice interviewer that can conduct screening calls with candidates, following a structured question flow.
- **Streamlit Dashboard**: A lightweight alternative dashboard for quick data visualization and management.

## 🏗️ Project Structure

- `app/`: FastAPI backend and core logic (Scoring, LLM, Database).
- `frontend/`: Next.js 15 web application.
- `pipecat-quickstart/`: Real-time voice interview agent sub-project.
- `tests/`: End-to-end and unit tests.

## 🛠️ Quick Start

### Backend (FastAPI)
1. `cd app`
2. `python -m venv venv`
3. `source venv/bin/activate` (or `.\venv\Scripts\activate` on Windows)
4. `pip install -r requirements.txt`
5. `uvicorn app.main:app --reload`

### Frontend (Next.js)
1. `cd frontend`
2. `npm install`
3. `npm run dev`

### Voice Agent (Pipecat)
See [pipecat-quickstart/README.md](./pipecat-quickstart/README.md) for detailed setup.

## 📄 Documentation

- [GEMINI.md](./GEMINI.md): Comprehensive onboarding and architecture guide.
- [COMMANDS.md](./COMMANDS.md): Useful development and deployment commands.
- [ANTIGRAVITY.md](./ANTIGRAVITY.md): Active task list and developer log.

---
Built with FastAPI, Next.js, Pipecat, and ❤️.
