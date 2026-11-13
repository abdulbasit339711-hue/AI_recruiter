# AI-Recruiter — System Evaluation Report

**Date:** 2026-06-12  ·  **Branch:** `refactor/generic-monorepo`  ·  **Scope:** backend, frontend, voice agent, repo hygiene

---

## Status update — 2026-11-13 (re-checked against the code)

This report is from 2026-06-12. Re-checked item by item; "fixed" means verified in the current source.

| Item (section) | Status now |
|---|---|
| Blocking SMTP on `POST /jobs/{id}/email` (3.1) | **Fixed** — sent as a background task (the endpoint returns "queued"; failures are logged, not returned) |
| Unbounded reprocess (3.1) | **Fixed** — `limit` (default 500, max 2000); call again while `remaining > 0` |
| Corrupt `status_history` dropped (3.1) | **Fixed** — preserved as a `recovered` timeline entry |
| Admin mutations unrate-limited (3.1) | **Fixed** — `admin_mutation_rate_ok` in the auth middleware |
| Worker skips deleted candidates (3.1) | **Partly** — logs a warning; still no dead-letter |
| "No Alembic on this side" (3.1) | **Stale** — backend uses Alembic (`alembic_version_backend`), idempotent migrations |
| `strict: false` in tsconfig (3.2) | **Fixed** — `strict: true` |
| EventSource has no reconnect (3.2) | **Fixed** — `lib/sse.ts` retries with backoff + jitter |
| Hardcoded `hr@company.com` (3.2) | **Fixed** — uses `getHrActor()`; identity is typed by the operator, not verified (no per-user accounts) |
| SSE payload validation (3.2) | Not re-checked |
| Voice API keys not validated at startup (3.3) | **Fixed** — `runner.py` checks required keys |
| Judge async-task leak; dropped rapid answers (3.3) | **Fixed** — tasks tracked, evaluations serialised by a lock, short answers no longer filtered out |
| Finalization race on re-open (3.3) | **Fixed** — per-session cross-thread lock |
| LLMContext setup errors swallowed (3.3) | Not re-checked |
| `COPY ./.env` in the voice Dockerfile (3.4) | **Fixed** — removed; inject env at runtime |
| No CI (3.4) | **Fixed** — `.github/workflows/ci.yml` |
| Unpinned base image (3.4) | **Open** — `voice-agent/server/Dockerfile` still `FROM dailyco/pipecat-base:latest` |
| Stale deps `groq==0.9.0`, `sentence-transformers==3.0.1` (3.4) | **Open** |
| PostCSS advisory (3.2) | Not re-checked |
| **Leaked API keys not rotated (P0)** | **Cannot be verified from the repo** — rotation happens at the providers. A scan of tracked files and git history found no real keys in common formats (Groq/OpenAI/Google patterns, key assignments), but that does not prove rotation. Rotate before showing this to anyone. |

New since this report: DOCX résumés, consent capture, `LOCAL_ONLY` mode, bias test, per-customer HR-platform tokens,
per-job interview length, score-explanation view, speaker timeline. See `docs/HR_EVALUATION_GUIDE.md` for what
automation does and does not do.

---

## 1. Executive Summary

AI-Recruiter is a **mature, well-architected** three-component system (FastAPI scoring backend, Next.js 15 HR dashboard, Pipecat voice-interview agent) sharing one Postgres/SQLite database. The codebase is clean, documented (mirrored CLAUDE/GEMINI/ANTIGRAVITY guides), and shows real engineering discipline: fail-closed auth, per-job scoring weights, circuit breaker + LLM fallback, resilient TTS, session-resume on restart, and a maintained error runbook.

**Overall grade: B+ / production-capable with caveats.** The architecture is sound and the happy path is well-tested. The blockers are **operational, not architectural**: a leaked-secrets exposure that needs key rotation, a blocking-SMTP availability bug, async-safety gaps in the voice judge pipeline, and missing CI. None require redesign.

| Component | Grade | Headline |
|-----------|-------|----------|
| Backend (FastAPI) | B+ | Solid scoring engine; blocking SMTP + unbounded reprocess are availability risks |
| Frontend (Next.js) | B+ | Secrets handled correctly server-side; `strict:false` + no SSE validation |
| Voice agent (Pipecat) | B | Strong reliability features; async task leaks & finalization races |
| Repo hygiene | B | Clean git tree & docs; **live secrets on disk** + Dockerfile bakes `.env`; no CI |

---

## 2. Architecture (as-built)

```
HR admin ──► Next.js dashboard ──► /api/admin proxy (injects ADMIN_API_TOKEN server-side)
                                         │
                                         ▼
                                  FastAPI backend (:8000)
                                  jobs + candidates tables
                                  3-tier scoring pipeline ──► in-process threaded worker
                                         │  (shared Postgres)
                                         ▼
                                  Pipecat voice agent (:7860)
                                  runner.py (HTTP) ──spawns──► per-room bot (STT→LLM→TTS)
                                  reads candidate scores; writes interview_sessions/*
```

**DB ownership split** (key contract): backend owns `jobs`/`candidates`; voice agent owns `interview_sessions`/`session_transcripts`/`session_goals`/`session_metrics`, linked by external VARCHAR `session_id`. Backend reads voice tables directly — column changes there are breaking changes.

---

## 3. Component Findings

### 3.1 Backend (FastAPI) — `app/`
**Strengths:** 38-endpoint surface with fail-closed shared-token auth (`core/auth.py`), per-IP rate limiting on public routes, explicit CORS allowlist. Scoring engine is well-built: Tier 1 regex/structure rules (/30) with hard-reject for irrelevant docs, Tier 2 cosine similarity with cached JD embeddings (/40), Tier 3 Groq LLM (/30) **gated** by Tier1+2 threshold, wrapped in a circuit breaker with deterministic keyword-overlap fallback and token/cost tracking. Per-job tier weights are configurable. Migrations are idempotent additive SQL (no Alembic on this side).

**Issues:**
- **Blocking SMTP in `POST /jobs/{id}/email`** (`main.py:~1035`) — synchronous `smtplib` in a loop blocks the event loop; tens of seconds with large shortlists. *Availability bug.*
- **`POST /jobs/{id}/reprocess`** (`main.py:~749`) enqueues all candidates synchronously — no pagination; HTTP timeout / queue flood on large jobs.
- **Worker skips deleted candidates silently** (`queue/worker.py:~66`) — candidate deleted between enqueue and pickup → pipeline skipped, no error, no dead-letter.
- **Corrupt `status_history` JSON silently dropped** (`main.py:~505`) — bare-except on `json.loads` loses audit trail.
- **Admin mutation endpoints have no rate limit** — only `/upload` and `/jobs` are limited; a token holder can spam mutations.

### 3.2 Frontend (Next.js 15) — `frontend/`
**Strengths:** **Admin-token handling is correct** — token lives only in server-side env and is injected by the `/api/admin/[...path]` proxy; never shipped to the browser bundle; auth via httpOnly `admin_session` cookie + middleware gate. React Query + Zustand are used idiomatically, error interceptor surfaces FastAPI `detail`, CSV export escapes correctly, polished UI (Radix/Tailwind/Framer). `package-lock.json` **is** committed.

**Issues:**
- **`strict: false` in tsconfig** (`tsconfig.json:11`) — disables `noImplicitAny`/`strictNullChecks`; type safety effectively off.
- **No runtime validation of SSE payloads** (`hooks/useInterviewLive.ts`, `useCandidateEvaluation.ts`) — raw JSON `as`-cast into state; malformed event can corrupt UI.
- **Hardcoded `"hr@company.com"` author** (`components/candidates/CandidateActions.tsx:41,71`) — HR audit trail is meaningless; doesn't use the logged-in identity.
- **EventSource has no reconnect** — a network blip permanently freezes live updates.
- **PostCSS moderate advisory** via Next.js's vendored version (npm audit).

### 3.3 Voice agent (Pipecat) — `voice-agent/server/`
**Strengths:** Correct process model — run `runner.py` (HTTP + per-room bot spawn), not `bot.py`. Strong reliability layer: resilient TTS degrades to text-only on quota (402), idle-STT noise suppressed, deterministic resumable `session_id`, status-aware resume (completed→deny, active/interrupted→resume w/ transcript replay). Alembic migrations are clean and self-healing. Good happy-path tests + maintained `ERRORS_AND_SOLUTIONS.md`.

**Issues:**
- **API keys not validated at startup** (`runner.py:~868`, `bot_manager.py:~138`) — empty `DEEPGRAM/GROQ/CARTESIA` keys init silently, fail mid-interview with cryptic errors.
- **Judge processor async-task leak** (`judge_processor.py:66`) — fire-and-forget `create_task` with no tracking/cancellation; tasks outlive the worker and may write to a closed pool / finalized session.
- **Finalization race on fast re-open** (`runner.py:~1084–1120`) — draining bot + new bot can both finalize the same `session_id` (last write wins). `create_session` is idempotent but `overall_assessment` is not serialized.
- **Judge eval gate drops rapid answers** (`judge_processor.py:73`) — `_evaluating` boolean skips overlapping evals silently; no queue.
- **LLMContext setup errors swallowed** (`bot_manager.py:~252`) — interview proceeds without the system persona; silent quality collapse.

### 3.4 Repo hygiene — root
**Strengths:** Clean git tree — no committed `.db`/logs/`__pycache__`; generated artifacts untracked and gitignored. Excellent Makefile DX. Root pins exact (`==`) deps; `uv.lock` committed; docs trio kept byte-identical with a sync footer. Refactor to generic monorepo appears complete.

**Issues:**
- **Live API keys on disk** in `.env` and `voice-agent/server/.env` (Groq, Deepgram, Cartesia, LiveKit, Gmail SMTP app password). *Correctly gitignored and never committed*, but real and currently readable — must be rotated if these files have ever left the machine (CI, container, backup, screen-share).
- **Dockerfile bakes secrets** — `voice-agent/server/Dockerfile:21` does `COPY ./.env ./.env`, embedding keys into image layers (`docker history` readable). **Confirmed.**
- **Unpinned base image** — `FROM dailyco/pipecat-base:latest`.
- **No CI** — no `.github/workflows`; pytest/eslint exist but nothing runs them on push.
- **Some stale deps** — `groq==0.9.0`, `sentence-transformers==3.0.1`.

---

## 4. Top Priorities

### P0 — do now
1. **Rotate the leaked keys** (Groq, Deepgram, Cartesia ×2, LiveKit, Gmail SMTP). They are plaintext in two `.env` files; treat as compromised.
2. **Stop baking secrets into the image** — remove `COPY ./.env ./.env` from the Dockerfile; inject env at runtime (compose env_file / `--secret`).

### P1 — this week
3. **Fix blocking SMTP** — move `POST /jobs/{id}/email` to async (`aiosmtplib`) or the background queue.
4. **Validate voice API keys at startup** — fail fast instead of mid-interview.
5. **Fix judge async-task leak** — track tasks in a set, cancel on worker shutdown.
6. **Add CI** — lint (ruff/eslint) + pytest on PR; pin the Docker base image.

### P2 — this sprint
7. Paginate/background the reprocess endpoints; rate-limit admin mutations.
8. Serialize per-`session_id` finalization (per-session lock) in the voice agent.
9. Frontend: enable `strict` (incrementally), add zod validation on SSE payloads, propagate real HR identity, add EventSource reconnect.
10. Bump stale deps (groq, sentence-transformers) behind tests.

---

## 5. What's Notably Good
- Layered scoring with a **gated** expensive tier and a graceful fallback — cost-aware and resilient.
- **Correct** secret boundary in the frontend (server-only token injection).
- Voice reliability engineering: resumable sessions, degrade-to-text TTS, idle-STT handling, error runbook.
- Clean monorepo with synced multi-agent docs and a regenerable module graph.

*Severities are based on a read-only code review; runtime/load behavior was not exercised.*
