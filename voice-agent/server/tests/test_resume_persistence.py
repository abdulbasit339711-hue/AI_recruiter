# test_resume_persistence.py
#
# Integration test for interview RESUME-ON-RESTART against a REAL Postgres. Proves the
# actual machinery a re-opened link relies on:
#   - the 0005 resume-progress columns exist (current_question_index, question_states)
#   - save_session_progress / get_session_progress round-trip (incl. JSONB states)
#   - get_transcript replays both sides in sequence order
#   - get_session_status drives the AUTHORITATIVE resume flag (active/interrupted=resume)
#   - InterviewSession.restore_progress + BotManager._resume_context_summary together
#     land the bot on the correct NEXT question after a restore
#
# Self-contained: inserts throwaway interview_sessions rows with unique session_ids and
# deletes them in teardown (session_transcripts cascade on FK). Auto-skips when Postgres
# is unreachable so it stays green without a DB.

import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from dotenv import load_dotenv

load_dotenv(override=True)

from database import DatabaseConfig, db_manager  # noqa: E402
from interview_session import (  # noqa: E402
    InterviewSession, RecruiterConfig, InterviewQuestion, InterviewGoal,
    AnswerDepth, GoalStatus,
)

# One shared module-scoped loop so the asyncpg pool is created once and reused
# (see the note in test_finalization_db_integration.py).
pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module", autouse=True, loop_scope="module")
async def _isolate_db_pool():
    """Ensure this module builds its OWN asyncpg pool on its OWN event loop.

    asyncpg pools and asyncio.Lock bind to the loop that created them. A pool left
    over from a prior DB-test module is bound to that module's now-closed loop, so
    reusing it raises 'attached to a different loop' / 'Event loop is closed'. We
    can't await-close that stranded pool (its loop is dead), so just orphan it here
    — synchronously, no await — and let _ensure_pool() rebuild a fresh pool on the
    current loop on the first DB call."""
    db_manager.pool = None
    db_manager._init_lock = asyncio.Lock()
    yield


def _refresh_config_from_env():
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


def _two_question_config() -> RecruiterConfig:
    return RecruiterConfig(
        job_role="Backend Engineer", company_name="Acme", interview_type="technical",
        system_prompt="You are an interviewer.",
        questions=[
            InterviewQuestion(id="q1", text="Tell me about a recent project.",
                              goal_id="g1", expected_depth=AnswerDepth.MEDIUM, expected_theme="project"),
            InterviewQuestion(id="q2", text="Describe a hard bug you fixed.",
                              goal_id="g2", expected_depth=AnswerDepth.MEDIUM, expected_theme="debugging"),
        ],
        goals=[
            InterviewGoal(id="g1", label="experience", description="d", weight=0.5),
            InterviewGoal(id="g2", label="problem solving", description="d", weight=0.5),
        ],
    )


@pytest_asyncio.fixture(loop_scope="module")
async def session_id():
    if not await _db_available():
        pytest.skip("Postgres not reachable — skipping resume persistence integration test")
    sid = f"itest-resume-{uuid.uuid4().hex[:12]}"
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


async def test_progress_roundtrip_persists_index_and_states(session_id):
    """save_session_progress → get_session_progress returns the same position + JSONB states."""
    states = {
        "q1": {"status": "covered", "follow_up_count": 1, "asked_at": None, "answered_at": None},
        "q2": {"status": "pending", "follow_up_count": 0, "asked_at": None, "answered_at": None},
    }
    await db_manager.save_session_progress(session_id, 1, states)

    prog = await db_manager.get_session_progress(session_id)
    assert prog is not None
    assert prog["current_question_index"] == 1
    assert prog["question_states"]["q1"]["status"] == "covered"      # JSONB parsed to dict
    assert prog["question_states"]["q1"]["follow_up_count"] == 1
    assert prog["question_states"]["q2"]["status"] == "pending"


async def test_get_session_progress_absent_returns_none():
    """A session that never existed has no persisted progress."""
    assert await db_manager.get_session_progress(f"nope-{uuid.uuid4().hex}") is None


async def test_session_status_drives_resume_detection(session_id):
    """The authoritative resume flag = prior status in (active, interrupted)."""
    def resumed(status):  # mirrors bot_manager.configure_session
        return status in ("active", "interrupted")

    assert await db_manager.get_session_status(session_id) == "active"
    assert resumed(await db_manager.get_session_status(session_id)) is True

    await db_manager.mark_session_status(session_id, "interrupted")
    assert resumed(await db_manager.get_session_status(session_id)) is True

    # A first-time join has no row at all → not a resume.
    missing = await db_manager.get_session_status(f"nope-{uuid.uuid4().hex}")
    assert missing is None
    assert resumed(missing) is False

    # A completed interview is spent, not resumable.
    assert resumed("completed") is False


async def test_transcript_replays_both_sides_in_order(session_id):
    """get_transcript returns the persisted conversation ordered by sequence_number."""
    await db_manager.add_transcript_entry(session_id, {"speaker": "agent", "text": "Hello, welcome."})
    await db_manager.add_transcript_entry(session_id, {"speaker": "candidate", "text": "Hi, thanks."})
    await db_manager.add_transcript_entry(session_id, {"speaker": "agent", "text": "Tell me about a project."})

    turns = await db_manager.get_transcript(session_id)
    assert [(t["speaker"], t["text"]) for t in turns] == [
        ("agent", "Hello, welcome."),
        ("candidate", "Hi, thanks."),
        ("agent", "Tell me about a project."),
    ]


async def test_full_restore_lands_on_next_question(session_id):
    """End-to-end: persist progress as the flow would, then restore onto a FRESH session
    (as configure_session does on re-open) and confirm the bot resumes on q2, not q1."""
    cfg = _two_question_config()

    # Simulate the first run: q1 asked + answered, advanced to q2.
    live = InterviewSession(session_id=session_id, config=cfg)
    live.mark_question_asked("q1")
    live.mark_question_answered("q1", GoalStatus.COVERED)
    live.advance_question()
    await db_manager.save_session_progress(
        session_id, live.current_question_index, live.progress_snapshot()
    )

    # Re-open: brand-new session object restored purely from the DB.
    restored = InterviewSession(session_id=session_id, config=cfg)
    prog = await db_manager.get_session_progress(session_id)
    restored.restore_progress(prog["current_question_index"], prog["question_states"])

    assert restored.current_question_index == 1
    assert restored.question_states["q1"].status == GoalStatus.COVERED
    assert restored.current_question is not None and restored.current_question.id == "q2"

    # The LLM resume instruction should name the covered topic and point at q2.
    from bot_manager import BotManager
    summary = BotManager._resume_context_summary(restored)
    assert "do NOT restart" in summary
    assert "Tell me about a recent project." in summary   # covered topic listed
    assert "Describe a hard bug you fixed." in summary     # next question named
