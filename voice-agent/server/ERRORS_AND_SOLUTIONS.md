# Voice Agent — Errors & Solutions Runbook

A reference of errors hit in the Pipecat voice agent (`voice-agent/server/`)
and how they were resolved. Grouped by area. Search this file by the error text
before debugging from scratch.

Legend: **Symptom** = what you see in logs · **Cause** = root cause · **Fix** =
resolution · **Where** = file(s) involved.

---

## 1. Dependencies / environment

### `AsyncClient.__init__() got an unexpected keyword argument 'proxies'`
- **Symptom:** crash constructing `AsyncGroq(...)` from `groq/_base_client.py`.
- **Cause:** old `groq==0.4.0` passes `proxies=` to `httpx`, but `httpx>=0.28` removed it.
- **Fix:** upgrade groq (`groq>=0.13.0`; resolved to 1.4.0) → `uv sync`. The
  `chat.completions.create` API is unchanged, so no code changes needed.
- **Where:** `pyproject.toml`.

---

## 2. Process / startup

### uvicorn exits with `sys.exit(1)` during startup
- **Symptom:** traceback ends in `uvicorn/server.py ... startup ... sys.exit(1)`.
- **Cause:** port **7860** already held by a stale `runner.py` process.
- **Fix:** kill it, then restart:
  ```bash
  kill -9 $(lsof -tiTCP:7860 -sTCP:LISTEN) 2>/dev/null; echo done
  ```
- **Where:** OS / process, not code.

---

## 3. Database & migrations (PostgreSQL)

> Schema is managed by **Alembic** (`alembic/`). Child tables link by the external
> `interview_sessions.session_id` (VARCHAR), never the internal `id` UUID.

### `permission denied for table interview_sessions` / `permission denied for schema public`
- **Cause:** fresh DB where the one-time bootstrap was never run — objects are
  owned by `postgres` and the app connects as `ai_user` with no grants.
- **Fix:** run the idempotent bootstrap script (creates role + DB if missing,
  applies grants, migrates). Safe to re-run:
  ```bash
  uv run python scripts/bootstrap_db.py
  ```
  It uses `DB_SUPERUSER`/`DB_SUPERUSER_PASSWORD` from `.env` for this step only.
  Peer-auth fallback (no superuser password):
  ```bash
  sudo -u postgres psql -d ai_recruiter -f alembic/bootstrap.sql
  uv run alembic upgrade head
  ```
  `alembic upgrade head` on an un-bootstrapped DB now fails fast with this hint
  instead of a raw traceback (see `alembic/env.py`).
- **Where:** `scripts/bootstrap_db.py`, `alembic/bootstrap.sql`, `alembic/env.py`.

### `password authentication failed for user "postgres"`
- **Cause:** `database.py` builds the global `db_manager` (reading `DB_*`) **at import
  time**. If a local module is imported before `load_dotenv()` runs, `.env` isn't
  loaded yet and it falls back to the default `postgres` / empty password.
- **Fix:** call `load_dotenv(override=True)` **before** importing `bot_manager_dual` /
  `database`. Also added `db_manager._ensure_pool()` lazy init as a safety net.
- **Where:** `runner.py` (import order), `database.py` (`_ensure_pool`).

### `Database not initialized`
- **Cause:** the connection pool was never created — usually a downstream effect of a
  failed `initialize()` earlier in the SAME process (e.g. the postgres-auth bug
  above), or an HTTP request arriving before `start()` finished.
- **Fix:** restart the process after fixing the real init error. `db_manager` now
  lazily creates the pool on first query (`_ensure_pool`) and surfaces the real
  connection error instead of this generic message.
- **Where:** `database.py`.

### `operator does not exist: character varying = uuid`
- **Cause:** child tables (`session_goals`, `session_transcripts`, `session_metrics`)
  declared `session_id` as `UUID`, but the code links by the external VARCHAR
  `session_id`; the `update_session_goal_stats` trigger and the `session_overview`
  view then compared `varchar = uuid`.
- **Fix:** child `session_id` columns are `VARCHAR(100) REFERENCES
  interview_sessions(session_id)`; view joins use `s.session_id = child.session_id`.
- **Where:** `alembic/versions/0001_initial_schema.py`. Convention: any new
  session-linked column must be `VARCHAR(100)` FK to `interview_sessions(session_id)`.

### `duplicate key value violates unique constraint "interview_sessions_session_id_key"`
- **Cause:** dual-pipeline initializes the same session more than once (a frame-driven
  init race).
- **Fix:** `create_session` is idempotent (`ON CONFLICT (session_id) DO UPDATE …
  RETURNING id`) and the processor sets a synchronous `_initializing` guard so only
  one init task is spawned.
- **Where:** `database.py`, `processors/goal_tracking_processor.py`.

### `invalid input for query argument $4 ... (expected datetime, got 'str')`
- **Cause:** Pipecat frame timestamps are epoch seconds (often stringified, e.g.
  `'1780839898.95'`) but the `timestamp` column is `TIMESTAMP`.
- **Fix:** `_coerce_timestamp()` converts epoch/ISO/datetime → `datetime` before insert.
- **Where:** `database.py`.

---

## 4. Goal tracking / broadcasting

### `Object of type Decimal is not JSON serializable`
- **Cause:** Postgres `NUMERIC` columns (progress_score, average_progress, cost_usd …)
  return Python `Decimal`, which `json.dumps` rejects — broke every SSE broadcast that
  carried goal data.
- **Fix:** broadcaster serializes with a `default` encoder (`Decimal→float`,
  `datetime→isoformat`).
- **Where:** `events/broadcaster.py` (`_json_default`).

### `unsupported operand type(s) for +: 'decimal.Decimal' and 'float'`
- **Cause:** `_apply_goal_update` added a float delta to `progress_score` (a `Decimal`)
  → threw, so **goal progress never persisted** (stayed `0.00` / `not_started`).
- **Fix:** `float()`-coerce current progress; clamp delta to `[-0.3, 0.3]` and result
  to `[0, 1]`.
- **Where:** `services/goal_tracking_service.py`.

### `Analysis failed: Expecting value: line 1 column 1 (char 0)`
- **Cause:** the analysis LLM returned empty / markdown-wrapped text; `json.loads` blew up.
- **Fix:** request Groq JSON mode (`response_format={"type":"json_object"}`) and parse
  defensively with `_safe_json_loads` (strips ``` fences, extracts `{…}`, returns `{}`).
- **Where:** `services/goal_tracking_service.py`.

### Judge scores everything 10/10 / scores "don't know" highly
- **Cause:** `JudgeProcessor` was a stub — a `MockCompletion` scoring by **word count**,
  never calling an LLM.
- **Fix:** real Groq call (`llama-3.1-8b-instant`) with the judge system prompt, JSON
  mode, and `_safe_json_loads`.
- **Where:** `judge_processor.py`.

### Transcript can't tell applicant from bot
- **Cause:** `/chat` (manual-input) text was labelled `"agent"` — same as the bot's
  replies. (A `TranscriptionFrame` is always applicant speech; the bot's words are TTS
  TextFrames labelled `agent` by `WorkingMetricsProcessor`.)
- **Fix:** label all `TranscriptionFrame`s as `"candidate"`; also let goal analysis
  process manual-input so typed conversations exercise goal tracking.
- **Where:** `processors/goal_tracking_processor.py`. Dashboard already styles
  `candidate` (right/blue) vs `agent` (left/dark).

### Final assessment never saved / `interview_sessions.overall_assessment` always NULL
- **Cause:** `BotManager.finalize_session()` was dead code — defined but never called,
  so the comprehensive end-of-interview analysis never ran, and even the on-demand
  `POST /goals/{session_id}/analyze` result was only returned, never persisted.
- **Fix:** `finalize_session()` is now invoked in `runner._make_and_run_bot` after the
  worker ends (covers disconnect / idle / cancel), for real interviews only.
  `finalize_session_goals()` persists the analysis via `db_manager.finalize_session_record()`
  → sets `status='completed'`, `ended_at`, `duration_seconds`, `overall_assessment`.
  Persist is skipped if analysis returns `{"error": ...}` so a record is never clobbered.
- **Also fixed:** `finalize_session()` used to call `close_database()` — that closes the
  process-global pool shared by every concurrent bot and the HTTP API. Removed; the pool
  is owned by process shutdown, not by one interview ending.
- **Where:** `runner.py`, `bot_manager_dual.py`, `processors/goal_tracking_processor.py`,
  `database.py`. Tests: `test_session_finalization.py`.

### Note: adaptive questioning is API-only by design — not dead code
- `AdaptiveQuestioningProcessor` is NOT added to the live pipeline. It is reached on
  demand via `goal_processor.get_adaptive_question_suggestion()` →
  `GET /goals/suggest-question` (a dashboard assist). The live interview is free-form
  LLM + goal tracking; there is no scripted question-flow in `BotManager` to auto-drive
  (`QuestionFlowProcessor` lives only in the legacy `bot.py`). Don't "remove it as dead
  code" — it's a working manual feature. Auto-driving the live LLM with it is a product
  decision, not a cleanup.
- **Where:** `processors/adaptive_questioning_processor.py`, `runner.py` (`/goals/suggest-question`).

---

## 5. Voice services (STT / TTS)

### Deepgram `1011 ... did not receive audio` / `keepalive ping timeout` / `Connection lost, will retry`
- **Cause:** Deepgram closes the socket after ~10s with no audio (KeepAlive alone is
  insufficient — it needs ≥1 audio message). Happens during text-only testing (no mic)
  or while the bot is speaking. **Non-fatal** — Deepgram auto-reconnects.
- **Fix:** suppressed as known self-healing noise via a loguru filter; real STT errors
  still show. (For pure text testing, STT isn't needed at all — `/chat` works over HTTP.)
- **Where:** `runner.py` (`_suppress_idle_stt_noise`).

### `keepalive ping failed` / `data transfer failed` + `AssertionError` from `websockets/legacy/protocol.py`
- **Cause:** the Deepgram SDK uses websockets' **deprecated legacy client**, which logs
  benign teardown tracebacks (via stdlib `logging`) when a connection drops.
  `websockets` is already latest (16.0) — the bug is in the legacy module itself, so
  upgrading does NOT help.
- **Fix:** silence that logger: `logging.getLogger("websockets").setLevel(CRITICAL)`.
- **Where:** `runner.py`.

### Cartesia `status 402: quota_exceeded` ("Insufficient credits") — TTS stops mid-session
- **Cause:** Cartesia account ran out of credits; every turn then 402s and spams
  ErrorFrames.
- **Fix (code):** `ResilientCartesiaTTSService` swallows Cartesia ErrorFrames, disables
  TTS for the session on a quota error, and lets the interview continue **text-only**
  (agent text is still broadcast before TTS). No spam, no repeated 402s.
- **Fix (account):** top up / enable overages at
  https://play.cartesia.ai/subscription.
- **Where:** `resilient_tts.py`, `runner.py`.

---

## 6. Networking (LiveKit)

### `region fetch timed out` / `signal connection timed out` / `restarting connection… attempt N`
- **Symptom:** `livekit::rtc_engine - failed to connect: Signal(RegionError(...))`,
  repeated resume/restart attempts.
- **Cause:** the machine lost (or never had) connectivity to LiveKit Cloud
  (`*.livekit.cloud`). A `ping timeout` drops the session, then region re-fetch fails.
  **Environmental — not a code bug.** The LiveKit client auto-retries.
- **Fix:** check this machine's network / VPN / firewall to `*.livekit.cloud`. Verify
  reachability:
  ```bash
  curl -sS -m 5 -o /dev/null -w "%{http_code}\n" https://<your-project>.livekit.cloud
  ```
  For pure **text testing**, LiveKit instability doesn't block you — `/chat` injection,
  transcript, and goal tracking work over HTTP regardless. LiveKit's Rust SDK logs
  print straight to stderr and can't be filtered from Python.

---

## 7. Tests

### `pytest` fails to collect: `cannot import name 'BotConnectedFrame' ... (unknown location)` / `'pipecat' is not a package`
- **Symptom:** each test file passes when run alone, but `uv run pytest` (whole
  suite) errors during collection on a `pipecat` import.
- **Cause:** `test_question_flow.py` used to inject fake `pipecat`/`loguru` modules
  into the global `sys.modules` at import time (a leftover from before pipecat was
  installed). That poisoned every sibling test that imports the *real* pipecat
  (e.g. `test_voice_auth.py` → `runner`). The mock was also incomplete (no
  `BotConnectedFrame`), so even its own target broke.
- **Fix:** pipecat is a declared dependency — import it for real; don't stub
  `sys.modules`. Removed the mock setup from `test_question_flow.py`.
- **Where:** `test_question_flow.py`.

### `async def test_*` silently skipped / "coroutine was never awaited"
- **Cause:** no asyncio plugin, so pytest collected async tests but never ran them
  (they only executed via each file's `__main__` block).
- **Fix:** added `pytest-asyncio` (dev group) + `asyncio_mode = "auto"` under
  `[tool.pytest.ini_options]` in `pyproject.toml`. Now `async def test_*` runs
  with no per-test marker.
- **Where:** `pyproject.toml`.

### `test_voice_auth.py` 401 tests fail with `assert 200 == 401`
- **Cause:** the operator guard is OFF by default and only enforced when
  `VOICE_REQUIRE_AUTH` is truthy (`runner._voice_auth_required()`). The test set
  `ADMIN_API_TOKEN` but not `VOICE_REQUIRE_AUTH`, so the guard never activated.
  This is a test-config gap, **not** a security hole — open-by-default is the
  intended local-dev behaviour; the real applicant boundary is the signed link.
- **Fix:** set `VOICE_REQUIRE_AUTH=true` (alongside `ADMIN_API_TOKEN`) at the top
  of the test. Both flags are read lazily via `os.getenv()` per request.
- **Where:** `test_voice_auth.py`.

---

## Quick reference: which entrypoints / files

- App entry: `runner.py` (FastAPI + Pipecat worker; logging filters; service setup).
- Pipeline assembly: `bot_manager_dual.py` (single/dual; STT→…→LLM→TTS).
- Goal tracking: `services/goal_tracking_service.py`, `processors/goal_tracking_processor.py`.
- DB access: `database.py`; schema/migrations: `alembic/` (see `alembic/README.md`).
- TTS resilience: `resilient_tts.py`. Broadcasting: `events/broadcaster.py`.
- Manual text testing: `POST /chat`; sample convo + replay in `test_conversations/`.
