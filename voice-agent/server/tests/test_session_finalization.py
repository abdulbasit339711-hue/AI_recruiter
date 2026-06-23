# test_session_finalization.py
#
# Unit tests for the wired-up session finalization path
# (GoalTrackingProcessor.finalize_session_goals). Fully mocked — no live DB, no
# network. Guards the persist-on-success / skip-on-error contract added when
# finalization was hooked into the bot lifecycle (runner._make_and_run_bot).

from unittest.mock import AsyncMock, MagicMock

import pytest

import processors.goal_tracking_processor as gtp
from processors.goal_tracking_processor import GoalTrackingProcessor


def make_processor():
    session = MagicMock()
    session.session_id = "sess-123"
    session.config = None  # prevents MagicMock > int comparison in phase1_boundary check
    goal_service = MagicMock()
    goal_service.comprehensive_goal_analysis = AsyncMock()
    broadcaster = MagicMock()
    broadcaster.broadcast = AsyncMock()
    proc = GoalTrackingProcessor(session, goal_service, broadcaster, groq_api_key="x")
    proc.goals_initialized = True
    return proc, goal_service, broadcaster


async def test_finalize_persists_and_broadcasts_on_success(monkeypatch):
    proc, goal_service, broadcaster = make_processor()
    analysis = {"overall_assessment": {"goal_coverage_rate": 0.8, "candidate_performance": 0.7}}
    goal_service.comprehensive_goal_analysis.return_value = analysis

    persist = AsyncMock()
    monkeypatch.setattr(gtp.db_manager, "finalize_session_record", persist)

    await proc.finalize_session_goals()

    # Persisted exactly once, with the session_id and the analysis as JSON.
    persist.assert_awaited_once()
    args = persist.await_args.args
    assert args[0] == "sess-123"
    assert "goal_coverage_rate" in args[1]  # JSON-encoded analysis
    # And still broadcast to the dashboard.
    broadcaster.broadcast.assert_awaited_once()
    assert broadcaster.broadcast.await_args.args[0] == "session_goals_finalized"


async def test_finalize_skips_persist_on_analysis_error(monkeypatch):
    proc, goal_service, broadcaster = make_processor()
    goal_service.comprehensive_goal_analysis.return_value = {"error": "LLM failed"}

    persist = AsyncMock()
    monkeypatch.setattr(gtp.db_manager, "finalize_session_record", persist)

    await proc.finalize_session_goals()

    # Never overwrite the record with an error blob...
    persist.assert_not_awaited()
    # ...but the error result is still broadcast for visibility.
    broadcaster.broadcast.assert_awaited_once()


async def test_finalize_noop_when_goals_uninitialized(monkeypatch):
    proc, goal_service, broadcaster = make_processor()
    proc.goals_initialized = False

    persist = AsyncMock()
    monkeypatch.setattr(gtp.db_manager, "finalize_session_record", persist)

    await proc.finalize_session_goals()

    goal_service.comprehensive_goal_analysis.assert_not_awaited()
    persist.assert_not_awaited()
    broadcaster.broadcast.assert_not_awaited()


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_finalize_persists_and_broadcasts_on_success(pytest.MonkeyPatch()))
    asyncio.run(test_finalize_skips_persist_on_analysis_error(pytest.MonkeyPatch()))
    asyncio.run(test_finalize_noop_when_goals_uninitialized(pytest.MonkeyPatch()))
    print("\n✅ Session finalization tests passed")
