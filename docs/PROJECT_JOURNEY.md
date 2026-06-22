# AI-Recruiter — Project Journey & Reference

A narrative record of how this codebase was evaluated, hardened, and extended in one
focused engineering arc. Written as a **reference for future projects**: the patterns,
decisions, and pitfalls here generalize beyond AI-Recruiter.

Companion docs: `SYSTEM_EVALUATION.md` (fault audit), `PROJECT_REPORT.md` (state +
improvement plan), `P3_PLAN.md` (larger initiatives).

---

## 0. Starting point

A working but unaudited three-component system: FastAPI scoring backend, Next.js 15 HR
dashboard, and a Pipecat voice-interview agent over a shared Postgres/SQLite DB. The brief
was open-ended: "evaluate the system and make a report," which then expanded into fixing
what the evaluation found and building a new pre-application IQ screen.

**Lesson:** an open-ended "evaluate X" is best answered by *first producing a written
audit*, then letting the user prioritize. The audit becomes the backlog.

---

## 1. Evaluate before touching (the audit)

Approach: parallel read-only exploration of each component (backend, frontend, voice,
repo hygiene), each returning concrete `file:line` findings, then a single synthesized
report graded by severity. Output: `docs/SYSTEM_EVALUATION.md`.

What it surfaced (the backlog that drove everything after):
- **P0 security:** real API keys sitting in `.env` on disk; the voice Dockerfile baked
  `.env` into image layers.
- **Availability:** blocking SMTP in a sync route; an unbounded `reprocess` endpoint.
- **Silent failures:** worker skipping deleted candidates; corrupt `status_history`
  dropped; voice judge fire-and-forget tasks leaking; LLM-context errors swallowed.
- **Quality/DX:** frontend `strict: false`; no CI; hardcoded audit identity; unvalidated
  SSE payloads.

**Lessons:**
- Verify the audit's scariest claims yourself before acting (we confirmed the Dockerfile
  `COPY ./.env` and that no real `.env` was git-tracked — the agent had one false alarm
  about a missing lockfile).
- Grade by severity and separate "I can fix this in code" from "human must act"
  (key rotation can only be done in provider dashboards — say so plainly and repeatedly).

---

## 2. Fix in waves, smallest-blast-radius first

Order mattered: each wave was independently committed and verified.

1. **Two headline fixes first** — non-blocking batch SMTP (one reused connection via
   `run_in_threadpool`) and removing `COPY ./.env` from the Dockerfile (+ `.dockerignore`).
2. **The fault batch** — admin-mutation rate limiting (central, in the auth middleware so
   no route is missed), bounded+resumable `reprocess`, worker handles deleted candidates,
   `status_history` corruption preserved not dropped, voice fail-fast key validation,
   judge async-task tracking+cancel, TS `strict: true` (only 1 real bug surfaced),
   defensive SSE parsing, login-captured audit identity, **GitHub Actions CI**, and
   `pyjwt` promoted to an explicit dependency.

**Lessons:**
- Put cross-cutting guards (auth, rate limits) in *one* enforcement point, not per-route.
- Turning on a strictness flag (`strict: true`) is cheap insurance — measure the error
  count first (`tsc --strict` reported exactly 1) to decide if it's a quick win or a project.
- A fix that "stops new leaks" is not the same as "un-leaks" — be explicit about residual risk.

---

## 3. Build the feature: the IQ screen, in layers

The pre-application IQ test was built incrementally, each layer shippable:

1. **Core (generic MCQ, server-scored, recorded-never-blocks):** a static question bank
   (`app/iq/bank.py`) + two stateless signed JWTs — a *test* token (pins served question
   ids + a server-enforced deadline) and a *result* token (carries the score). No session
   table. Correct answers never leave the server. Score attaches at upload via an optional
   form field; absent/invalid token simply leaves it null.
2. **Time-weighted scoring:** time measured *server-side* (issuance → submit, can't be
   forged), folded in as `accuracy × (1 − speed_weight × time_used_fraction)`.
3. **Per-question detail:** an `iq_details` column; the applicant UI clocks each question
   and submits per-question times; the breakdown (chosen vs correct + time) is embedded in
   the result token and rendered in the HR drawer.
4. **Surfacing:** IQ shown in the candidate table, Kanban, CSV, the detail drawer, and a
   new **Profile section** in the downloadable report.

**Key design decisions (all the user's calls, captured here so they're not re-litigated):**
- **Static bank, not LLM-generated.** The user explicitly wanted deterministic, randomized
  questions — not LLM cost/latency. (I briefly started toward LLM generation on a misread;
  reverting was cheap because each layer was isolated.)
- **Generic, not per-job.** One shared bank for all jobs.
- **Recorded, never gates.** IQ is informational for HR ranking, never blocks an applicant.

**Lessons:**
- **Stateless signed tokens** (JWT) are a powerful pattern for carrying trusted data across
  a multi-request flow (test → submit → upload) without a session table. Mirror an existing
  codec (we reused the interview-link token shape) so signing/secret handling stays uniform.
- Keep the secret on the server: ship questions without answers (`to_public()`), score
  server-side, and only let a *signed* result ride back through the client.
- Build features in **shippable layers** — core first, then enrich (time, then detail).
  A later misread cost nothing because layers didn't entangle.

---

## 4. Prove it with the real system, not just unit tests

Beyond 65 passing tests, the work was validated against the running stack:
- **Live audio interview** end-to-end (IQ → résumé upload → LiveKit room → real Groq/
  Deepgram turns → per-answer judge → finalize → assessment), driven by a committed harness
  (`scripts/live_interview_e2e.py`). This exercised voice code that unit tests can't (the
  finalization lock and judge queue I'd changed actually ran).
- **Real résumé sweep** through the 3-tier pipeline (`scripts/e2e_mock_drive.py`): graded
  résumés scored in order; edge cases (corrupt/empty/oversized) rejected gracefully.
- **Demo population:** ran the IQ→upload flow for every active job so each had a candidate
  with real companies + IQ, then backfilled the rest for a fully-populated panel.

**Lessons:**
- Some classes of bug only appear in the live system (stale dev servers, port conflicts,
  external-service auth). Keep a **committed e2e driver** so "run the real thing" is one
  command.
- When a sandbox lacks a dependency (pipecat here), check for an existing venv before
  declaring something untestable — the voice suite ran fine under its own `uv` venv.

---

## 5. The operational pitfalls (where the time actually went)

These are the unglamorous problems that recur in every project:

- **CI green locally ≠ green in CI.** Three separate failures: (a) `pytest tests/` couldn't
  `import app` because the console-script invocation doesn't add CWD — fixed with a root
  `pytest.ini` (`pythonpath = .`); (b) tests assumed a pre-populated DB — fixed by creating
  the schema in `conftest.py`; (c) `npm ci` rejected the lockfile due to optional native-dep
  (`@emnapi`) drift across npm major versions — switched CI to `npm install`.
- **Tests polluting the shared DB.** `test_iq.py` created "IQ Job" rows in the real Postgres
  every run (85 accumulated). Root cause fix: a root `conftest.py` that points the suite at
  an ephemeral SQLite file. *Tests must own their database.*
- **Stale dev servers.** "CSS is failing" turned out to be a zombie `next dev` on :3000
  serving a 9-byte stylesheet while a second instance held :3001. The config was fine; the
  process was stale. Fix: kill all, start one.
- **Background processes that don't persist.** `nohup … &` didn't survive in this harness;
  the tool's `run_in_background` did. Know your runtime's process model.

**Lessons:**
- Reproduce the *exact* CI invocation locally (`pytest tests/`, not `python -m pytest`).
- When something "is broken," first ask *which instance / which environment* — a surprising
  share of "bugs" are stale state, not code.
- Make tests hermetic: own the DB, reset global singletons (we added `reset_rate_limits()`
  for the in-process limiter windows).

---

## 6. Data hygiene as you go

Demo/testing accumulates junk. We removed 85 "IQ Job" rows + their candidates, then 5 more
named test jobs, then content-less test candidates — while explicitly **keeping** real data
(a genuine résumé correctly Rejected) and the demo the user still had a link to. Reprocessed
all active jobs to refresh scores; confirmed IQ data survived re-scoring.

**Lesson:** when cleaning data, enumerate what you're deleting and why, and protect anything
the user is actively referencing. Prefer the app's own archive/delete semantics.

---

## 7. What generalizes (the checklist for the next project)

1. **Audit first**, write it down, let severity drive the order.
2. **Verify scary claims** before acting; separate code-fixable from human-only.
3. **Fix in small, independently-committed waves.**
4. **Central enforcement** for cross-cutting concerns (auth, rate limits).
5. **Stateless signed tokens** to carry trusted data across multi-step flows.
6. **Ship features in layers**; keep them decoupled so a wrong turn is cheap.
7. **Tests own their DB**; reset global state; reproduce CI's exact invocation.
8. **Keep a committed e2e driver** and validate against the real system.
9. **"Broken" is often stale state** — check the instance/environment first.
10. **Be explicit about residual risk** (e.g. rotate-the-keys) and repeat it until done.

---

## 8. Still open

- **P0:** rotate the leaked API keys (provider dashboards) — only thing code can't do.
- **P3 backlog** (`P3_PLAN.md`): real auth + roles, PII encryption/retention, dependency
  refresh, IQ integrity hardening.
