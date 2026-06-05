"""Tests for candidate SSE event hub."""
from app.events.broadcaster import CandidateEvent, event_hub


def test_candidate_event_terminal_flags():
    ev = CandidateEvent(
        candidate_id=1,
        job_id=2,
        status="Shortlisted",
        terminal=True,
        total_score=82.5,
    )
    data = ev.to_json()
    assert '"candidate_id": 1' in data
    assert '"terminal": true' in data


def test_subscribe_queues_created():
    assert isinstance(event_hub._queues, dict)
