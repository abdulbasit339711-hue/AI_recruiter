# AI-Recruiter — Project Report & Improvement Plan

**Date:** 2026-06-12 · **Branch:** `refactor/generic-monorepo` · **Latest commit:** `a5f68bb`

This report covers (1) what the system is and how it's built, (2) its current health,
(3) the improvements made in this work cycle, and (4) a prioritized roadmap of what's
left. It complements `docs/SYSTEM_EVALUATION.md` (the raw fault audit).

---

## 1. What the system is

AI-Recruiter is a multi-tier automated recruitment platform with three deployable
components over one shared database:

| Component | Stack | Port | Responsibility |
|-----------|-------|------|----------------|
| **Backend** | FastAPI + SQLAlchemy | 8000 | Job CRUD, résumé intake, 3-tier scoring, HR ops, SSE, email/invite, **IQ screen** |
| **Frontend** | Next.js 15 + React 19 | 3000 | HR admin dashboard + public applicant/interview UI |
| **Voice agent** | Pipecat (STT→LLM→TTS) | 7860 | Real-time AI screening interviews over WebRTC/LiveKit |

**Database:** SQLite by default, PostgreSQL via `DATABASE_URL`. Backend owns
`jobs`/`candidates`; the voice agent owns `interview_sessions` + child tables, linked by
an external VARCHAR `session_id`. The backend reads the voice tables directly to render
interview results — an implicit cross-service contract.

### The candidate journey

```
Applicant ── views job ──► IQ screen (NEW) ──► résumé upload ──► queued
                                                                    │
                              3-tier scoring pipeline (background worker)
                              Tier 1 profile rules (spaCy)      /30
                              Tier 2 semantic similarity (MiniLM)/40
                              Tier 3 LLM eval (Groq, gated)     /30
                                                                    │
HR dashboard ◄── ranked candidates ◄── scores + IQ + summary written back
     │
     └─ invite ──► AI voice interview ──► transcript + per-answer judge scores ──► HR review
```

### The 3-tier scoring engine (the core IP)

- **Tier 1 — Profile rules** (`scoring/tier1.py`): regex/structure extraction of
  email/phone/education/experience/skills; hard-rejects irrelevant documents.
- **Tier 2 — Semantic similarity** (`scoring/tier2.py`): cosine similarity of résumé vs
  JD embeddings (`all-MiniLM-L6-v2`), JD embeddings cached (FIFO, content-hash key).
- **Tier 3 — LLM evaluation** (`llm/groq_client.py`): Groq `llama-3.3-70b-versatile`,
  **gated** — only runs when Tier1+Tier2 ≥ threshold (cost control), wrapped in a circuit
  breaker with a deterministic keyword-overlap fallback. Token usage + cost tracked.
- Per-job **tier weights** and all thresholds live in `config.yaml`.

### Notable existing strengths

- Cost-aware scoring (expensive tier is gated + has a graceful fallback).
- Correct frontend secret boundary: the admin token is injected server-side by the
  `/api/admin` proxy and never reaches the browser bundle.
- Voice reliability engineering: resumable sessions, degrade-to-text TTS on quota,
  idle-STT handling, a maintained `ERRORS_AND_SOLUTIONS.md` runbook.
- Clean monorepo with synced agent docs (CLAUDE/GEMINI/ANTIGRAVITY) and a regenerable
  module dependency graph.

---

## 2. Current health

| Area | Status |
|------|--------|
| Backend tests | **57 passing** (`pytest tests/`) |
| Frontend | **TypeScript `strict` clean, ESLint clean** |
| CI | GitHub Actions added (backend + frontend + shared) |
| Type safety | strict mode now on (was off) |
| Known blocker | **Leaked API keys not yet rotated** (must be done in provider dashboards) |

Overall: **production-capable**. The architecture is sound; the remaining work is
incremental hardening and a few latent correctness items, not redesign.

---

## 3. Improvements delivered this cycle

### 3.1 New feature — pre-application IQ screen

A short, **server-scored, timed** aptitude test taken before résumé upload. Per the
chosen design: **recorded, never blocks** the application; **built-in question bank** now,
structured to become per-job configurable later.

- **`app/iq/`** — `bank.py` (built-in questions; correct answers never serialized) and
  `tokens.py` (two stateless, signed JWTs — a *test* token pinning served questions + a
  server-enforced deadline, and a tamper-proof *result* token carrying the score). No
  session table needed; mirrors the existing interview-link token pattern.
- **Endpoints** — `GET /iq-test` (sampled questions + test token), `POST /iq-test/submit`
  (scores server-side → result token). Both public (apply flow), added to the backend
  auth allowlist and the Next proxy allowlist.
- **Persistence** — `Candidate.iq_score/iq_correct/iq_total` columns + migration; `/upload`
  accepts an optional `iq_token` form field and attaches the score (absent/invalid/
  mismatched token → null, never blocks).
- **Frontend** — `IqTest.tsx` (one question at a time, per-question countdown,
  auto-advance, graceful skip if unavailable); the apply page is now a 2-step flow. Score
  surfaced in the HR **candidate table**, **detail drawer**, and **CSV export**.
- **Tests** — `tests/test_iq.py` (17): bank scoring, token round-trip/tamper/expiry,
  endpoints, and the upload-attach / never-block behavior.

### 3.2 Reliability & security fixes (from the fault audit)

| Fix | Detail | Files |
|-----|--------|-------|
| **Non-blocking batch email** | Was a new SMTP connection + TLS + login *per recipient* inside a sync loop; now one reused connection run via `run_in_threadpool`. Response contract preserved. | `app/services/email.py`, `app/main.py` |
| **Dockerfile secret baking** | Removed `COPY ./.env`; added `.dockerignore` so secrets can't enter image layers. | `voice-agent/server/Dockerfile`, `.dockerignore` |
| **Admin mutation rate-limiting** | A leaked admin token could spam every PUT/PATCH/DELETE/POST. Now limited centrally in the auth middleware. | `app/core/ratelimit.py`, `app/core/auth.py` |
| **Bounded reprocess** | `POST /jobs/{id}/reprocess` no longer loads/commits every candidate unbounded; capped + resumable (`remaining`). | `app/main.py` |
| **Worker handles deleted candidate** | Was a silent no-op; now logs + skips cleanly. | `app/queue/worker.py` |
| **Preserve corrupt audit trail** | Corrupt `status_history` JSON was silently dropped; now preserved as a recovery entry. | `app/main.py` |
| **Voice key validation** | Empty `DEEPGRAM/GROQ/CARTESIA` keys failed mid-interview; now fail fast at startup. | `voice-agent/server/runner.py` |
| **Voice judge task leak** | Fire-and-forget `create_task` outlived the worker; now tracked + cancelled on cleanup. | `voice-agent/server/processors/judge_processor.py` |
| **TS strict mode** | Enabled `strict: true` (was off); fixed the one real type bug it surfaced. | `frontend/tsconfig.json`, `useUpdateJob.ts`, `api.ts` |
| **SSE payload validation** | Raw `JSON.parse` + `as`-casts could crash listeners / corrupt state; now defensively parsed & shape-guarded. | `frontend/src/hooks/useInterviewLive.ts` |
| **Real audit identity** | Hardcoded `hr@company.com` → operator identity captured at login (localStorage), since there are no per-user accounts. | `frontend/src/lib/actor.ts`, login page, `CandidateActions.tsx` |
| **CI** | Added GitHub Actions: backend pytest, frontend lint/typecheck/build, shared-package tests. | `.github/workflows/ci.yml` |
| **Dependency hygiene** | `pyjwt` promoted to an explicit `requirements.txt` dep (was only transitive via the editable shared package). | `requirements.txt` |

---

## 4. Improvement roadmap (what's left)

### P0 — do immediately (out-of-band)
- **Rotate the leaked API keys** (Groq, Deepgram, Cartesia ×2, LiveKit, Gmail SMTP). The
  code now prevents *new* leaks, but the existing keys are already exposed on disk and
  must be rotated in each provider's dashboard. Then move to a secrets manager / runtime
  injection (the `.dockerignore` + Dockerfile changes already support `--env-file`).

### P1 — near-term hardening
- **Pin the Docker base image** — `dailyco/pipecat-base:latest` → a specific tag.
- **Fix the broken Dockerfile COPY** — it copies `./local_bot.py`, which doesn't exist
  (only `runner.py` does); the image build is currently broken independent of secrets.
- **Replace the in-process queue & SSE hub** — `queue/worker.py` and the SSE broadcaster
  are single-process/in-memory; they don't survive restarts or scale horizontally. Move to
  Celery/RQ + Redis (or a managed queue) and a shared pub/sub for multi-instance.
- **Swap hand-rolled backend migrations for Alembic** — `database.py` uses a hand-maintained
  list of `ALTER TABLE` strings; the voice agent already uses Alembic. Unify on it so new
  columns don't require a manual `run_migrations()` step.

> **IQ test is intentionally generic.** One shared question bank serves all jobs (by
> design — no per-job editor). The bank can still grow over time, but it is not
> job-specific. Future bank growth is content work, not an architecture change.

### P2 — robustness & quality

These are correctness/operability gaps that don't block today's happy path but cause
silent data loss, degraded UX, or hard-to-diagnose failures under load or edge cases.

**Voice agent**
- *Serialize per-session finalization.* When a candidate disconnects, their bot is marked
  "draining" and torn down. If they reopen the link within the drain window, a second bot
  can spawn while the first is still writing its final `overall_assessment` — both write the
  same `session_id` row and the last write wins (assessment data can be lost). Fix: an
  `asyncio.Lock` keyed by `session_id` around finalization so exactly one bot finalizes.
- *Replace the judge's single-flight gate.* `JudgeProcessor` uses a boolean `_evaluating`
  that early-returns while an evaluation is running, so if a candidate gives several quick
  answers only the first is scored — the rest are dropped with no log. Fix: queue answers
  (or cancel-old-on-new) so every substantial answer gets a judge score.
- *Fail loudly on LLM-context setup errors.* If loading the system persona into the LLM
  context throws, it's logged and swallowed; the interview then runs with no persona and
  produces erratic replies while the candidate sees nothing wrong. Fix: abort/raise so the
  failure is visible instead of silently degrading interview quality.

**Backend**
- *Input validation & size caps.* Job `job_description`/`llm_prompt` and IQ answer payloads
  accept arbitrary size; a multi-MB JD can break Tier-2 embeddings and waste compute. Add
  length/shape limits.
- *Status enum.* Candidate status is stringly-typed (`S.QUEUED` constants mixed with literal
  `"Pending"`/`"Processed"`); a typo won't be caught. Model it as an `Enum` for safety.
- *Connection-pool tuning.* The SQLAlchemy pool uses defaults; under many concurrent
  requests + the background worker, connections can be exhausted. Set `pool_size` /
  `max_overflow` for the target load.

**Frontend**
- *EventSource auto-reconnect.* SSE streams close on any network blip and never reconnect,
  so live score/interview updates freeze until a manual refresh. Add exponential-backoff
  reconnect (or a heartbeat + re-subscribe).
- *Runtime payload schemas.* Now that `strict` is on, validate server payloads with zod at
  the boundary for end-to-end type safety (the SSE handlers are already hardened; extend to
  REST responses).

**Observability**
- Wire the existing `/metrics` endpoint to a dashboard (Prometheus/Grafana), add structured
  logs, and alert on circuit-breaker-open and TTS-degraded states so operators see silent
  degradation early.

### P3 — product / scale

Larger initiatives that change the product's posture (compliance, multi-user, currency).

- **Real authentication.** Today a single shared admin token gates everything, so there's no
  per-user identity — the audit trail's `changed_by` is self-reported (now captured at login,
  but not verified). Introduce per-user accounts (SSO/OAuth or a users table + sessions) so
  actions are attributable, access is revocable per person, and roles can be enforced.
- **PII handling.** Résumés, emails, and raw extracted text are stored in plaintext —
  candidate personal data. Add encryption-at-rest and a retention/deletion policy
  (e.g. right-to-erasure), which most hiring deployments require legally.
- **Dependency refresh.** `groq==0.9.0` and `sentence-transformers==3.0.1` are a year+ behind,
  missing fixes and features; upgrade now that CI can catch regressions.
- **IQ-screen integrity (if it becomes higher-stakes).** The test is generic, but if results
  start gating decisions you'd want: option-order shuffling, a larger bank with per-attempt
  sampling, tighter timing, one-attempt enforcement keyed to email, and basic proctoring
  signals (e.g. tab-switch detection). All are integrity measures on the generic test — not
  per-job customization.

---

## 5. Quick reference — where things live

| Concern | Path |
|---------|------|
| API routes | `app/main.py` |
| Scoring engine | `app/scoring/`, `app/llm/` |
| IQ screen | `app/iq/`, `frontend/src/components/applicant/IqTest.tsx` |
| Auth + rate limiting | `app/core/auth.py`, `app/core/ratelimit.py` |
| Background worker / SSE | `app/queue/worker.py`, `app/events/` |
| Voice interview server | `voice-agent/server/runner.py` (run this, not `bot.py`) |
| Shared token/role/status codecs | `packages/shared/recruiter_shared/` |
| CI | `.github/workflows/ci.yml` |
| Fault audit | `docs/SYSTEM_EVALUATION.md` |
