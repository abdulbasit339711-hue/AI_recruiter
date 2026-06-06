# 🤖 ANTIGRAVITY Developer Guide & Active Tasks

This document serves as the active hand-off file and status report for **Antigravity AI Coding Assistants** working on this codebase.

---

## 📌 Active Context Summary

We have transitioned from a single-job configuration to a **Multi-Job Management** platform.
- **Database Schema**: Safely migrated via programmatic raw SQL executed in FastAPI's startup event (`app/main.py`), appending `job_id` to the `candidates` table and creating the `jobs` table.
- **FastAPI Endpoints**: CRUD endpoints configured for `/jobs` (Create, List, Retrieve, Update, Soft-Archive) and `/upload` updated to link candidates to jobs.
- **Scoring Pipeline**: Engine modified to query job-specific JDs and custom prompts from SQLite.
- **UI Dashboard**: Refactored Streamlit frontend to display leaderboard per job, soft-archive jobs, edit job parameters, and upload candidates directly to selected active jobs.

---

## 🛠️ Environment Constraints

> [!WARNING]
> **Network Rate-Limiting**: The workspace environment experiences connections timeouts with PyPI.
> All pip commands must use increased timeouts and retry limits:
> ```powershell
> .\venv\Scripts\pip.exe install -r requirements.txt --default-timeout=1000 --retries 10
> ```

---

## 📝 Active Task List (Progress Log)

### Phase 1: Environment & Pip Stability
- [x] Create project structure & configurations
- [/] **In Progress**: Re-run pip package installation (Task ID `298b939a-8dad-4a57-bbc3-dcb022a6b195/task-152` is currently running).
- [ ] Verify spaCy model `en_core_web_sm` load/download flow on test execution.

### Phase 2: Schema Evolution & Multi-Job CRUD
- [x] Update `app/config.yaml` to extract global Job Descriptions.
- [x] Configure `Job` model and `job_id` foreign key mappings in `app/models.py`.
- [x] Implement database startup migration to alter `candidates` safely.
- [x] Build FastAPI Job CRUD endpoints in `app/main.py`.
- [x] Update `POST /upload` API endpoint to accept `job_id` query parameter.

### Phase 3: Job-Specific Scoring Adaptation
- [x] Modify `app/scoring/tier1.py` to pull weights dynamically.
- [x] Adapt `app/scoring/engine.py` to fetch database job targets dynamically.
- [x] Update `app/llm/groq_client.py` to dynamically utilize job-specific custom LLM prompts.

### Phase 4: Streamlit Job Dashboard (Module 400)
- [x] Add Job Selector dropdown to the main view to display leaderboards per job.
- [x] Implement Job Management Panels (Create Job, Edit Job, soft-archive job).
- [x] Modify Ingestion Portal to assign manual PDF uploads directly to the chosen active job.
- [x] Verify candidate history preservation for archived jobs (soft-archived jobs remain queryable).

### Phase 5: Verification & Testing
- [ ] Update `test_scoring.py` to configure mock jobs, assign candidates, and run multi-job rankings.
- [ ] Run `python test_scoring.py` to verify the new multi-job logic works end-to-end.
- [ ] Launch the dashboard with `streamlit run app/dashboard/app.py` for visual check.

### Phase 6: Next.js Frontend Dashboard (SKill.md integration)
- [x] Create SKill.md and establish frontend development standards.
- [x] Upgrade dependencies in `frontend/package.json` to support React 19, Tailwind CSS v4, and Lucide React.
- [x] Fix hydration/context providers error in `frontend/src/app/layout.tsx` by using a dedicated client-side `Providers` wrapper.
- [ ] Build global navigation and layout wrappers.
- [ ] Establish Axios client integrations with the FastAPI backend on port 8000.
- [ ] Create Zustand store for active job and candidate selectors.
- [ ] Build the interactive panels: Jobs CRUD panel, Resume Upload Zone, Candidate Leaderboard Table, Candidate Profile Deep-Dive.
- [ ] Build data export hooks (CSV & Markdown).
- [ ] Build SMTP email notification triggers.

---

## 🔮 Next Actions for Developer

1. **Obtain Plan Approval**: Wait for the user to review and approve the Next.js 15 upgrade implementation plan.
2. **Execute Frontend Setup**: Once approved, install frontend dependencies and run `npm run dev` to verify the dev environment.
3. **Resolve Hydration Bug**: Refactor `layout.tsx` to use the new client-side providers wrapper.
4. **Develop Dashboard Features**: Implement full frontend CRUD, file ingestion, scoring leaderboards, and candidate deep-dive views matching the aesthetic guidelines.

