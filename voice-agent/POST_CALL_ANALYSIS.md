# Technical Design: Post-Call Analysis & Dual-Evaluation Loop

This document outlines the architecture for high-fidelity transcript processing and the implementation of a dual-evaluation system to assess both the Candidate and the AI Agent.

---

## 🏗️ 1. Structured Transcript Persistence
After every call, the raw Pipecat `InterviewSession` is processed into a **Diarized JSON Schema**.

### Speaker Diarization
The system distinguishes between `AI_RECRUITER` and `APPLICANT`.

**JSON Output Template (`transcript_{session_id}.json`):**
```json
{
  "session_metadata": {
    "job_id": "job_123",
    "candidate_id": "cand_456",
    "duration_seconds": 1240,
    "timestamp": "2026-06-05T20:00:00Z"
  },
  "dialogue": [
    {
      "turn": 1,
      "speaker": "AI_RECRUITER",
      "text": "Can you describe a challenging technical problem you solved?",
      "question_id": "q1",
      "timestamp": "00:05"
    },
    {
      "turn": 2,
      "speaker": "APPLICANT",
      "text": "I recently migrated a monolith to microservices using Kubernetes...",
      "timestamp": "00:15"
    }
  ]
}
```

---

## ⚖️ 2. Dual-Evaluation Architecture

We implement two distinct "Judges" that run asynchronously after the call ends.

### Layer A: The Candidate Judge (Competency Scoring)
**Inputs**: JD, Question Flow, Applicant Answers.
*   **Goal**: Assign a final score based on the 3-Tier engine.
*   **Logic**: Did the applicant's answer for `q1` actually meet the requirements of the `Problem Solving` goal?
*   **Output**: Final score, executive summary, and "Proof of Skill" snippets.

### Layer B: The Meta-Evaluator (Bot Performance Judge)
**Inputs**: Applicant Answers, Bot Questions, In-Call LLM Critique.
*   **Goal**: Evaluate the AI Agent's performance to improve the prompt.
*   **Critique Matrix**:
    *   **Prompt Adherence**: Did the bot stick to the JSON format?
    *   **Context Awareness**: Did the bot ask a redundant follow-up if the user already answered the point?
    *   **Hallucination Check**: Did the bot invent facts about the company?
*   **Optimization Loop**: This evaluator generates a "Prompt Improvement Suggestion" (e.g., "The bot is too aggressive with follow-ups on short answers; suggest increasing the word-count threshold").

---

## 🛠️ Data Flow & Integration

1.  **Call End**: `runner.py` detects `status == completed`.
2.  **Export**: The `InterviewSession` object is serialized to the Diarized JSON format.
3.  **The "Judge" Hook**:
    *   **Step 1**: Send JSON to `scoring/engine.py` to update the central `candidates` table.
    *   **Step 2**: Send JSON to the **Meta-Evaluator** (new service).
4.  **Feedback Report**: A Markdown report is generated for HR, including:
    *   The diarized transcript.
    *   Candidate scores.
    *   **AI Quality Score** (Internal only).

---

## 🔜 Implementation Roadmap

### Phase 1: Diarization Utility
*   Implement `transcript_accumulator.export_json()` to convert `dataclass` turns into the schema above.

### Phase 2: Post-Call Judge Service
*   Create `app/llm/meta_evaluator.py`.
*   Develop a "System vs Agent" comparison prompt.

### Phase 3: Leaderboard Sync
*   Update the Next.js frontend to allow HR to download the Diarized JSON and view the "Meta-Critique" of the interview flow.

---

> **Strategic Note**: The Meta-Evaluator is the key to scaling. By having an AI judge the AI, we can automatically tune the interview questions without manually listening to thousands of hours of audio.
