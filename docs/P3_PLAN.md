# P3 Implementation Plan

**Status:** planning · **Prereqs:** P0 (rotate keys) done out-of-band; P1/P2 landed.

P3 items change the product's *posture* — compliance, multi-user, currency — rather than
patching a bug. Each is scoped below with goal, approach, touch-points, effort, and risks.
Recommended order: **1 → 2 → 3 → 4** (auth unblocks real audit + access control, which PII
work depends on).

---

## 1. Real authentication & authorization

**Goal:** replace the single shared admin token with per-user identity so actions are
attributable, access is revocable per person, and roles can be enforced.

**Current state:** one `ADMIN_API_TOKEN` gates everything (backend middleware
`app/core/auth.py`); the Next proxy injects it from a server-only env; `changed_by` is now
captured at login (`frontend/src/lib/actor.ts`) but **self-reported, not verified**.

**Approach (phased):**
- **Phase 1 — user store + sessions.** Add a `users` table (id, email, hashed_password
  [argon2/bcrypt], role, status, created_at). Replace the shared-token check with a session
  validator: issue a signed session cookie (JWT or server session) on login. Keep the
  existing admin token working as a break-glass fallback behind a flag during migration.
- **Phase 2 — roles.** Introduce roles (e.g. `admin`, `recruiter`, `viewer`) and enforce at
  the route layer (a `require_role(...)` dependency). Mutations require `recruiter+`; config
  (scoring weights, IQ bank) requires `admin`.
- **Phase 3 — real audit identity.** Derive `changed_by` server-side from the authenticated
  user (ignore client-supplied values) so the audit trail is trustworthy. Retire
  `lib/actor.ts`.
- **Phase 4 (optional) — SSO.** Add OAuth/OIDC (Google Workspace / Okta) for orgs that want
  it; the user store becomes the identity mapping.

**Touch-points:** `app/core/auth.py`, new `app/models.py` user model + migration, new
`/auth/login`/`/auth/logout` endpoints, `frontend/src/app/api/login`, `middleware.ts`, the
proxy (`/api/admin/[...path]`), and `changed_by` call sites.

**Effort:** L (Phase 1–3: ~3–5 days). **Risks:** session/cookie security (CSRF, secure
flags), migration without locking out current users (keep token fallback), password reset
flow. **Done when:** login is per-user, routes enforce roles, audit `changed_by` is
server-derived, and the shared token is removed.

---

## 2. PII handling — encryption & retention

**Goal:** protect candidate personal data (résumé text, emails, names, interview audio) and
support deletion, as most hiring deployments legally require (GDPR/CCPA-style).

**Current state:** `candidates.raw_text`, `email`, `name`, and interview transcripts/audio
are stored in plaintext; no retention or erasure mechanism.

**Approach:**
- **Encryption at rest.** Prefer DB/disk-level encryption (Postgres TDE or an encrypted
  volume) as the baseline — transparent, no app changes. For defense-in-depth on the most
  sensitive columns (`raw_text`, `email`), add application-level encryption via a KMS-managed
  key (envelope encryption) on a `EncryptedType` column. Audio files → encrypted object
  storage (S3 SSE) instead of a local `data/recordings` path.
- **Retention & erasure.** Add a retention policy (e.g. purge candidate PII N days after a
  terminal decision, configurable). Implement a `DELETE /candidates/{id}/pii` (admin-only)
  that nulls/overwrites PII columns and removes audio while keeping anonymized scores for
  analytics. A scheduled job enforces the time-based policy.
- **Access logging.** Log who viewed/exported résumé text (ties into #1).

**Touch-points:** `app/models.py` (encrypted columns / nullable PII), a KMS/secret
integration, `app/main.py` (résumé view/export, new erasure endpoint), recording storage in
`voice-agent/server/bot_manager.py::_save_recording`, a scheduled purge task.

**Effort:** M–L (~3–4 days, more with app-level column encryption). **Risks:** key management
(rotation, loss = data loss), search/sort over encrypted columns (keep score columns
plaintext), breaking the backend↔voice shared-table contract — coordinate schema changes.
**Done when:** PII is encrypted at rest, an erasure path exists, and a retention job runs.

---

## 3. Dependency refresh

**Goal:** get off year-old libraries (`groq==0.9.0`, `sentence-transformers==3.0.1`, and the
PostCSS advisory in the Next.js toolchain) now that CI can catch regressions.

**Approach:**
- Bump in small, testable batches behind the new CI: (a) `groq` — check the chat/completions
  API and circuit-breaker call sites in `app/llm/groq_client.py` + the voice judge; (b)
  `sentence-transformers` — verify Tier-2 embeddings still produce comparable scores (the
  e2e test mocks scoring, so add a quick real-model sanity check on a fixture); (c) frontend
  — resolve the PostCSS advisory via the Next.js upgrade path.
- Pin exact versions after each green batch; record any score drift from the embedding bump.

**Touch-points:** `requirements.txt`, `voice-agent/server/pyproject.toml` + `uv.lock`,
`frontend/package.json` + lockfile, `app/llm/groq_client.py`, `app/scoring/tier2.py`.

**Effort:** S–M (~1–2 days). **Risks:** Tier-2 score drift changes rankings (measure before/
after on a fixed résumé set); Groq SDK signature changes; Next major upgrade churn. **Done
when:** deps are current, CI is green, and any scoring drift is quantified and accepted.

---

## 4. IQ-screen integrity (only if it becomes higher-stakes)

**Goal:** if IQ results start influencing decisions, raise the bar against trivial cheating —
while keeping the test **generic** (one shared bank, not per-job).

**Approach (all integrity, not customization):**
- **Option-order shuffling.** Shuffle option order per served question; record the shuffle in
  the signed test token so server-side scoring still maps choices to the correct answer
  (`app/iq/bank.py` + `tokens.py`).
- **Bigger bank + sampling.** Grow the generic bank so each attempt samples a small subset
  from a large pool, reducing answer-sharing value. Pure content work.
- **One-attempt enforcement.** Bind an attempt to the candidate's email (and/or a cookie):
  refuse a fresh test token if a result already exists for that email+job within a window.
  Requires a light server record (or reuse the result token's `jti`).
- **Tighter timing & proctoring signals.** Shorter per-question windows; optional client
  signals (tab-switch/blur, paste detection) attached to the result for HR context — advisory,
  not blocking, consistent with "recorded, never gates."

**Touch-points:** `app/iq/bank.py`, `app/iq/tokens.py`, `app/main.py` (one-attempt check),
`frontend/src/components/applicant/IqTest.tsx` (timing + signals).

**Effort:** S–M (~1–2 days). **Risks:** false-positive proctoring penalizing honest users
(keep advisory); email-based gating is weak without accounts (revisit after #1). **Done
when:** option shuffling + sampling ship and one-attempt is enforced per the chosen key.

---

## Sequencing summary

| # | Item | Effort | Unblocks |
|---|------|--------|----------|
| 1 | Real auth + roles | L | trustworthy audit (#1.3), access logging (#2), email gating (#4) |
| 2 | PII encryption + retention | M–L | compliance posture |
| 3 | Dependency refresh | S–M | security patches; independent, can run in parallel |
| 4 | IQ integrity | S–M | only if IQ becomes decision-weighted |

Estimated total: ~8–12 engineering days, sequenced so auth lands first.
