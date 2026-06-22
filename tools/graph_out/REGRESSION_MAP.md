# Regression Impact Map

_Weighted dependency graph of the whole monorepo. "Impact" = blast radius if this module changes (fan-in × 2 + incoming refs)._

## Highest blast-radius modules — change these, retest dependents

### `fe:types/index.ts`  (frontend, impact 61)
- Depended on by **20** modules (21 refs):
  `fe:hooks/useCandidateEvaluation.ts`×2, `fe:hooks/useJobEvaluationEvents.ts`×1, `fe:components/admin/JobTable.tsx`×1, `fe:hooks/useUpdateJob.ts`×1, `fe:hooks/useUploadResume.ts`×1, `fe:hooks/useCreateJob.ts`×1, `fe:components/admin/JobFormModal.tsx`×1, `fe:components/job/JobCard.tsx`×1, `fe:hooks/useCandidate.ts`×1, `fe:components/admin/KanbanBoard.tsx`×1, `fe:hooks/useCandidates.ts`×1, `fe:lib/api.ts`×1 …(+8 more)

### `fe:lib/api.ts`  (frontend, impact 51)
- Depended on by **17** modules (17 refs):
  `fe:hooks/useJobEvaluationEvents.ts`×1, `fe:hooks/useUpdateJob.ts`×1, `fe:hooks/useArchiveJob.ts`×1, `fe:hooks/useUploadResume.ts`×1, `fe:components/admin/ResumeViewer.tsx`×1, `fe:hooks/useMetrics.ts`×1, `fe:components/candidates/InterviewPanel.tsx`×1, `fe:hooks/useCandidateEvaluation.ts`×1, `fe:hooks/useCreateJob.ts`×1, `fe:components/candidates/CandidateNotesPanel.tsx`×1, `fe:hooks/useCandidate.ts`×1, `fe:hooks/useCandidates.ts`×1 …(+5 more)

### `fe:components/ui/button.tsx`  (frontend, impact 39)
- Depended on by **13** modules (13 refs):
  `fe:components/admin/JobTable.tsx`×1, `fe:components/admin/ResumeViewer.tsx`×1, `fe:app/applicant/[jobId]/apply/success/page.tsx`×1, `fe:components/admin/JobFormModal.tsx`×1, `fe:components/candidates/CandidateNotesPanel.tsx`×1, `fe:app/admin/page.tsx`×1, `fe:app/page.tsx`×1, `fe:components/admin/KanbanBoard.tsx`×1, `fe:components/admin/CandidateTable.tsx`×1, `fe:app/applicant/[jobId]/apply/page.tsx`×1, `fe:components/candidates/CandidateActions.tsx`×1, `fe:app/admin/candidates/page.tsx`×1 …(+1 more)

### `app.database`  (backend, impact 30)
- Depended on by **10** modules (10 refs):
  `app.main`×1, `app.models`×1, `app.dashboard.app`×1, `app.llm.groq_client`×1, `app.llm.name_extractor`×1, `app.queue.worker`×1, `app.scoring.engine`×1, `app.scoring.tier1`×1, `app.scoring.tier2`×1, `app.scripts.migrate_sqlite_to_pg`×1

### `database`  (voice, impact 27)
- Depended on by **8** modules (11 refs):
  `runner`×4, `bot_manager_dual`×1, `session_factory`×1, `working_processors`×1, `processors.adaptive_questioning_processor`×1, `processors.goal_tracking_processor`×1, `services.goal_tracking_service`×1, `services.role_config_service`×1

### `interview_session`  (voice, impact 24)
- Depended on by **8** modules (8 refs):
  `bot`×1, `question_flow_processor`×1, `test_interview_session`×1, `test_question_flow`×1, `transcript_accumulator`×1, `processors.goal_tracking_processor`×1, `services.goal_tracking_service`×1, `services.role_config_service`×1

### `app.core`  (backend, impact 18)
- Depended on by **6** modules (6 refs):
  `app.main`×1, `app.dashboard.app`×1, `app.events.broadcaster`×1, `app.events.sse`×1, `app.queue.worker`×1, `app.scoring.engine`×1

### `fe:lib/utils.ts`  (frontend, impact 18)
- Depended on by **6** modules (6 refs):
  `fe:components/ui/textarea.tsx`×1, `fe:components/ui/button.tsx`×1, `fe:components/ui/dialog.tsx`×1, `fe:components/ui/card.tsx`×1, `fe:components/ui/table.tsx`×1, `fe:components/ui/input.tsx`×1

### `app.models`  (backend, impact 16)
- Depended on by **5** modules (6 refs):
  `app.queue.worker`×2, `app.main`×1, `app.dashboard.app`×1, `app.scoring.engine`×1, `app.scripts.migrate_sqlite_to_pg`×1

### `events.broadcaster`  (voice, impact 15)
- Depended on by **5** modules (5 refs):
  `bot`×1, `bot_manager_dual`×1, `question_flow_processor`×1, `runner`×1, `transcript_accumulator`×1

### `recruiter_shared`  (shared, impact 15)
- Depended on by **5** modules (5 refs):
  `app.interview_links`×1, `runner`×1, `services.goal_tracking_service`×1, `services.role_config_service`×1, `tests.test_shared`×1

### `services.goal_tracking_service`  (voice, impact 15)
- Depended on by **5** modules (5 refs):
  `bot_manager_dual`×1, `judge_processor`×1, `processors.adaptive_questioning_processor`×1, `processors.goal_tracking_processor`×1, `services.role_config_service`×1

### `app.core.model_registry`  (backend, impact 13)
- Depended on by **4** modules (5 refs):
  `app.main`×2, `app.core.jd_embedding_cache`×1, `app.scoring.tier1`×1, `app.scoring.tier2`×1

### `fe:components/admin/StatusBadge.tsx`  (frontend, impact 12)
- Depended on by **4** modules (4 refs):
  `fe:components/admin/JobTable.tsx`×1, `fe:components/admin/KanbanBoard.tsx`×1, `fe:components/admin/CandidateTable.tsx`×1, `fe:app/admin/candidates/page.tsx`×1

### `fe:components/ui/dialog.tsx`  (frontend, impact 12)
- Depended on by **4** modules (4 refs):
  `fe:components/admin/ResumeViewer.tsx`×1, `fe:components/admin/JobFormModal.tsx`×1, `fe:components/candidates/CandidateActions.tsx`×1, `fe:app/admin/candidates/page.tsx`×1

### `app.core.jd_embedding_cache`  (backend, impact 9)
- Depended on by **3** modules (3 refs):
  `app.main`×1, `app.scoring.engine`×1, `app.scoring.tier2`×1

### `app.events`  (backend, impact 9)
- Depended on by **3** modules (3 refs):
  `app.main`×1, `app.queue.worker`×1, `app.scoring.engine`×1

### `app.llm.groq_client`  (backend, impact 9)
- Depended on by **3** modules (3 refs):
  `app.main`×1, `app.llm.name_extractor`×1, `app.scoring.engine`×1

### `app.scoring.tier1`  (backend, impact 9)
- Depended on by **3** modules (3 refs):
  `app.scoring.engine`×1, `app.scoring.heuristics`×1, `app.scoring.tier2`×1

### `bot`  (voice, impact 9)
- Depended on by **3** modules (3 refs):
  `bot_manager_dual`×1, `session_factory`×1, `services.role_config_service`×1
