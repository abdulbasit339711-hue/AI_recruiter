# Technical Design: Competency-Based Goal Tracking

This document outlines the strategy for evolving the AI-Recruiter's goal tracking from simple keyword matching to a robust, semantic state machine.

---

## 🏗️ 3-Layer Evaluation Architecture

To ensure high-fidelity candidate assessment, the system should evaluate answers using three distinct layers of verification.

### 1. The 4-State Lifecycle (State Machine)
Each interview goal (e.g., "Technical Depth", "Team Collaboration") must follow a formal state progression:

| State | Definition | UI Visual |
| :--- | :--- | :--- |
| **PENDING** | Question hasn't been asked yet. | Gray Circle |
| **EXPLORING** | Question asked; AI is processing the first answer. | Pulsing Blue |
| **COVERED** | High-quality answer received; Goal met. | Green Check |
| **WEAK** | Answer was insufficient; Follow-up triggered. | Orange Warning |

### 2. Semantic Quality Gates (NLP Layer)
Replace fragile keyword checks with **Sentence Embeddings**.
*   **Engine**: Use a local transformer model (e.g., `all-MiniLM-L6-v2`).
*   **Logic**: Calculate the cosine similarity between the candidate's transcript and the `GoalDescription`.
*   **Threshold**: 
    *   `Score > 0.70`: Mark as **COVERED**.
    *   `Score < 0.40`: Mark as **WEAK** and trigger follow-up.

### 3. LLM Evidence Extraction (Reasoning Layer)
Utilize the LLM's `evaluation` JSON to extract concrete evidence for why a goal was marked as met.
*   **Example**: "Candidate successfully described the STAR method for resolving a merge conflict."
*   **Persistence**: Save this evidence to the `candidates` table in SQLite for post-interview review by HR.

---

## 📊 Dashboard Visualisation (Kanban Style)

The dashboard's "Goal Tracking" panel should be upgraded to a real-time progress board:

| Goal | Status | Key Evidence / Critique |
| :--- | :--- | :--- |
| **Problem Solving** | ✅ COVERED | Detailed migration from Monolith to Microservices. |
| **Communication** | 🟡 EXPLORING | Answer was a bit vague; awaiting follow-up. |
| **Culture Fit** | ⚪ PENDING | - |

---

## 🛠️ Implementation Roadmap

### Phase 1: State Machine Hardening
*   Update `InterviewSession.py` to include `evidence` and `semantic_score` fields in the state objects.
*   Broadcast `goal_update` SSE events on every turn.

### Phase 2: Embedding Integration
*   Add `sentence-transformers` to `pyproject.toml`.
*   Implement a `GoalEvaluator` utility that runs locally to minimize LLM costs and latency.

### Phase 3: SQLite Synchronization
*   Map the `GoalStatus` and `Evidence` back to the main `Candidates` table in the root database.
*   Allow HR to click a "View Evidence" button on the Next.js leaderboard.

---

> **Strategic Note**: Moving to semantic tracking prevents candidates from "gaming" the AI by simply repeating keywords from the job description.
