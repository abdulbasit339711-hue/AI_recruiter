# test_finalization_db_integration.py
#
# Integration test for the finalization DB write against a REAL Postgres. The
# mocked unit test (test_session_finalization.py) proves the persist/skip *logic*;
# this proves the actual SQL in db_manager.finalize_session_record() works against
# the live schema (status/ended_at/duration_seconds/overall_assessment).
#
# Safe + self-contained: it inserts a throwaway interview_sessions row with a unique
# session_id, asserts the finalize write, and deletes the row in teardown — it never
# touches real interview data. Auto-skips when Postgres is unreachable, so it stays
# green in environments without a DB (CI without services).

import asyncio
import json
import os
import uuid

import pytest
import pytest_asyncio
from dotenv import load_dotenv

load_dotenv(override=True)

from database import DatabaseConfig, db_manager  # noqa: E402

# asyncpg pools (and db_manager's init lock) bind to the event loop that created
# them. pytest-asyncio gives each test a fresh loop by default, which would strand
# the pool after the first test. Pin every test + fixture in this module to ONE
# shared module-scoped loop so the real pool is created once and reused.
pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module", autouse=True, loop_scope="module")
async def _isolate_db_pool():
    """Ensure this module builds its OWN asyncpg pool on its OWN event loop.

    Pools/locks bind to their creating loop; a pool left over from a prior DB-test
    module is bound to that module's now-closed loop and can't be reused or
    await-closed. Orphan any leftover here — synchronously, no await — so
    _ensure_pool() rebuilds a fresh pool on the current loop on the first DB call."""
    db_manager.pool = None
    db_manager._init_lock = asyncio.Lock()
    yield


def _refresh_config_from_env():
    # db_manager builds its config at import time; if .env loaded after that, refresh
    # it here (only safe while no pool exists yet — no other test opens a real pool).
    if db_manager.pool is None:
        db_manager.config = DatabaseConfig(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 5432)),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "ai_recruiter"),
        )


async def _db_available() -> bool:
    _refresh_config_from_env()
    try:
        await db_manager._ensure_pool()
        async with db_manager.pool.acquire() as c:
            return await c.fetchval("SELECT 1") == 1
    except Exception:
        return False


@pytest_asyncio.fixture(loop_scope="module")
async def session_row():
    if not await _db_available():
        pytest.skip("Postgres not reachable — skipping finalization DB integration test")
    sid = f"itest-final-{uuid.uuid4().hex[:12]}"
    async with db_manager.pool.acquire() as c:
        await c.execute(
            "INSERT INTO interview_sessions (session_id, role_type, status) "
            "VALUES ($1, $2, 'active')",
            sid, "backend-engineer",
        )
    try:
        yield sid
    finally:
        async with db_manager.pool.acquire() as c:
            await c.execute("DELETE FROM interview_sessions WHERE session_id = $1", sid)


async def test_finalize_session_record_writes_assessment_and_completes(session_row):
    sid = session_row
    assessment = json.dumps({
        "overall_assessment": {"goal_coverage_rate": 0.75, "candidate_performance": 0.6},
        "recommendation": "advance",
    })

    await db_manager.finalize_session_record(sid, assessment)

    async with db_manager.pool.acquire() as c:
        row = await c.fetchrow(
            "SELECT status, ended_at, duration_seconds, overall_assessment "
            "FROM interview_sessions WHERE session_id = $1",
            sid,
        )

    assert row["status"] == "completed"
    assert row["ended_at"] is not None
    assert row["duration_seconds"] is not None          # derived from started_at
    assert row["overall_assessment"] == assessment      # exact JSON round-trip


async def test_finalize_is_idempotent_and_preserves_first_end_time(session_row):
    sid = session_row
    await db_manager.finalize_session_record(sid, json.dumps({"v": 1}))
    async with db_manager.pool.acquire() as c:
        first_end = await c.fetchval(
            "SELECT ended_at FROM interview_sessions WHERE session_id = $1", sid
        )

    # Re-running keeps the original ended_at (COALESCE) but updates the assessment.
    await db_manager.finalize_session_record(sid, json.dumps({"v": 2}))
    async with db_manager.pool.acquire() as c:
        row = await c.fetchrow(
            "SELECT ended_at, overall_assessment FROM interview_sessions WHERE session_id = $1",
            sid,
        )

    assert row["ended_at"] == first_end
    assert json.loads(row["overall_assessment"]) == {"v": 2}
