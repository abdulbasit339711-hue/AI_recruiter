# 💼 AI-Recruiter: Multi-Job Recruitment MVP

Welcome to the **AI-Recruiter** system. This repository contains a complete, automated pipeline designed to ingest candidate PDF resumes, validate them, parse their text content, and score them against specific job openings using a **3-Tier Scoring Engine**.

---

## 🌟 Overview & System Architecture

AI-Recruiter is built with **FastAPI** (backend REST APIs), **SQLite** (relational database), and **Streamlit** (interactive dashboard).

```
                 +-----------------------+
                 |    HR Administrator   |
                 +-----------+-----------+
                             |  (Streamlit UI / APIs)
                             v
              +--------------+--------------+
              |     Job Management (CRUD)    |
              +--------------+--------------+
                             |
         +-------------------+-------------------+
         |                                       |
         v                                       v
+--------+--------+                     +--------+--------+
|   Jobs Table    |                     | Candidates Table|
| (JDs & Prompts) |                     |  (Scores & FK)  |
+--------+--------+                     +--------+--------+
         |                                       ^
         | (Matches JDs)                         | (Stores outputs)
         +---------------+                       |
                         v                       |
         +---------------+-----------------------+-------+
         |             3-Tier Scoring Pipeline           |
         |                                               |
         |  Tier 1: Profile Rules (Contact info, Secs)   |
         |  Tier 2: Semantic Similarity (Sentence-Trans) |
         |  Tier 3: Qualitative LLM Evaluation (Groq)    |
         +-----------------------------------------------+
```

---

## 📂 Project Structure

```
ai-recruiter/
├── .env                       # Local environment configurations (GROQ_API_KEY)
├── requirements.txt           # Python application dependencies
├── test_scoring.py            # Local evaluation and test framework
├── GEMINI.md                  # This onboarding documentation
├── ANTIGRAVITY.md             # Developer logs & active task status
└── app/
    ├── config.yaml            # Scoring weights, database URLs, and system limits
    ├── database.py            # SQLAlchemy setup, session helper, and config parser
    ├── models.py              # SQLite schema models (Job, Candidate)
    ├── main.py                # FastAPI routes (Jobs CRUD, PDF upload & parsing)
    ├── intake/
    │   └── upload.py          # PDF size validation, pdfplumber text extraction
    ├── scoring/
    │   ├── engine.py          # Main orchestrator running Tiers 1, 2, and 3
    │   ├── tier1.py           # Email, phone, and section keyword matching (spaCy)
    │   └── tier2.py           # Sentence-Transformers cosine similarity scoring
    └── llm/
        └── groq_client.py     # Groq API client with fallback simulation
```

---

## 📊 Database Schema

SQLite schema definition details:

### 1. `jobs` Table
Contains individual job openings, job descriptions (JD), and custom evaluation prompts:
* **id**: `INTEGER PRIMARY KEY AUTOINCREMENT`
* **title**: `TEXT` (Job role title)
* **department**: `TEXT` (e.g., Engineering, Sales)
* **job_description**: `TEXT` (The detailed requirements)
* **llm_prompt**: `TEXT` (Optional custom prompt for Tier 3 evaluation)
* **status**: `TEXT` (`Active` or `Archived` - soft-archived to preserve candidate history)
* **created_at**: `TEXT` (ISO-8601 creation timestamp)

### 2. `candidates` Table
Holds resumes linked to specific job profiles, along with processed scores and metadata:
* **id**: `INTEGER PRIMARY KEY AUTOINCREMENT`
* **filename**: `TEXT` (Uploaded PDF name)
* **email**: `TEXT` (Extracted contact email)
* **raw_text**: `TEXT` (Extracted search text)
* **job_id**: `INTEGER` (Foreign key referencing `jobs.id`)
* **tier1**: `REAL` (Profile rules score, out of 30)
* **tier2**: `REAL` (Semantic similarity score, out of 40)
* **tier3**: `REAL` (LLM qualitative score, out of 30)
* **total_score**: `REAL` (Sum of tier1 + tier2 + tier3, out of 100)
* **summary**: `TEXT` (LLM executive summary of fit)
* **evidence**: `TEXT` (JSON string array of matching evidence points)
* **status**: `TEXT` (`Pending`, `Processed`, `Failed`)
* **created_at**: `TEXT` (ISO timestamp)

---

## 🧮 The 3-Tier Scoring Engine

The scoring system evaluates candidates against JDs, with weights loaded dynamically from `app/config.yaml`:

1. **Tier 1: Profile Rules (Max 30 points)**
   - **Email detected**: +5 points (configurable via `email_weight`)
   - **Phone detected**: +5 points (configurable via `phone_weight`)
   - **Education section**: +7 points (configurable via `education_weight`)
   - **Experience section**: +7 points (configurable via `experience_weight`)
   - **Skills section**: +6 points (configurable via `skills_weight`)
   - Evaluated via spaCy linguistic scanning.

2. **Tier 2: Semantic Similarity (Max 40 points)**
   - Calculates the cosine similarity between the resume text and the job description using local `sentence-transformers` (`all-MiniLM-L6-v2`).
   - Mapped directly using the `semantic_weight` multiplier.

3. **Tier 3: Qualitative Fit (Max 30 points)**
   - Evaluates details and quality using the Groq API (defaults to `llama3-8b-8192` with structured JSON format).
   - Utilizes custom job prompts if configured.
   - **Fallback Simulator**: If `GROQ_API_KEY` is not active, the engine falls back to a simulated keyword-intersection calculator to prevent pipeline failure.

---

## 🚀 Setup & Execution Instructions

### 1. Initialize Virtual Environment & Dependencies
Create a virtual environment and install packages:
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt --default-timeout=1000 --retries 10
```

### 2. Configure Environment Variables
Create a file named `.env` in the root folder:
```env
GROQ_API_KEY=your_actual_groq_api_key_here
```
*(If left empty or as default, Tier 3 evaluations will automatically use the fallback simulation mode)*

### 3. Run FastAPI Backend
Start the uvicorn development server:
```powershell
uvicorn app.main:app --reload
```
Access docs & try endpoints at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### 4. Run Streamlit Dashboard
Launch the interactive web portal:
```powershell
streamlit run app/dashboard/app.py
```
This opens the candidate leaderboards, Job Operations Panel, and resume PDF intake portal in your browser.

### 5. Run Verification Tests
Verify local pipeline logic with mock data:
```powershell
python test_scoring.py
```
This initializes a test database, inserts mock jobs (Python Developer & Technical Project Manager), assigns mock resumes, and prints out sorted leaderboards for each job.

---

## 🎤 Pipecat Voice Agent (Sub-Project)

The project includes a real-time voice interview agent built with Pipecat. For specific details on its architecture, setup, and state management, see the **[Pipecat Sub-Project GEMINI.md](./pipecat-quickstart/GEMINI.md)**.
