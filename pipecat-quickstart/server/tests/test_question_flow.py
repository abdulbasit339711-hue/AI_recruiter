# test_question_flow.py
#
# Exercises QuestionFlowProcessor against the real pipecat install. We used to
# inject fake `pipecat`/`loguru` modules into sys.modules here, but that polluted
# the global import state and broke every sibling test that needs real pipecat
# (e.g. test_voice_auth.py). Pipecat is a declared dependency, so import it for
# real instead.

import asyncio
from unittest.mock import AsyncMock, MagicMock

from pipecat.processors.aggregators.llm_context import LLMContext

# ── Imports ───────────────────────────────────────────────────────────────────
from interview_session import (
    AnswerDepth,
    FollowUpPrompt,
    GoalStatus,
    InterviewGoal,
    InterviewQuestion,
    InterviewSession,
    InterviewStatus,
    RecruiterConfig,
)
from processors.question_flow_processor import (
    QuestionFlowProcessor,
    _answer_is_sufficient,
    _filler_ratio,
    _word_count,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_session() -> InterviewSession:
    config = RecruiterConfig(
        job_role="Backend Engineer",
        company_name="Acme",
        interview_type="technical",
        system_prompt="You are an interviewer.",
        questions=[
            InterviewQuestion(
                id="q1",
                text="Describe a hard problem you solved.",
                goal_id="problem_solving",
                expected_depth=AnswerDepth.LONG,
                expected_theme="problem solution outcome",
                follow_ups=[
                    FollowUpPrompt("Can you be more specific?", "too vague"),
                ],
            ),
            InterviewQuestion(
                id="q2",
                text="How do you handle team conflict?",
                goal_id="communication",
                expected_depth=AnswerDepth.MEDIUM,
                expected_theme="team communication resolution",
            ),
        ],
        goals=[
            InterviewGoal("problem_solving", "Problem Solving", "...", 0.6),
            InterviewGoal("communication", "Communication", "...", 0.4),
        ],
    )
    s = InterviewSession(candidate_id="c1", candidate_name="Test", config=config)
    s.start()
    return s


def make_processor(session):
    context = LLMContext()
    proc = QuestionFlowProcessor(session, context)
    proc.push_frame = AsyncMock()
    return proc, context


# ── Answer quality unit tests ─────────────────────────────────────────────────

def test_word_count():
    assert _word_count("hello world") == 2
    assert _word_count("") == 0
    print("✓ word count")


def test_filler_ratio():
    assert _filler_ratio("um uh like you know") > 0.5
    assert _filler_ratio("I solved the problem by refactoring the service") < 0.1
    print("✓ filler ratio")


def test_answer_sufficient_long():
    q = MagicMock()
    q.expected_depth = AnswerDepth.LONG
    q.expected_theme = "problem solution outcome"

    good = (
        "I was working on a distributed caching problem where our Redis cluster "
        "was causing latency spikes. I profiled the system, identified hot keys, "
        "and implemented a local L1 cache with TTL. The outcome was a 60 percent "
        "reduction in p99 latency and the solution went to production within a week."
    )
    assert _answer_is_sufficient(good, q)
    print("✓ sufficient long answer")


def test_answer_insufficient_short():
    q = MagicMock()
    q.expected_depth = AnswerDepth.LONG
    q.expected_theme = "problem solution outcome"
    assert not _answer_is_sufficient("I fixed a bug.", q)
    print("✓ insufficient short answer rejected")


def test_answer_insufficient_filler():
    q = MagicMock()
    q.expected_depth = AnswerDepth.MEDIUM
    q.expected_theme = "team communication resolution"
    filler_answer = " ".join(["um uh like basically"] * 10)
    assert not _answer_is_sufficient(filler_answer, q)
    print("✓ filler-heavy answer rejected")


# ── Flow logic tests ──────────────────────────────────────────────────────────

async def test_opening_question_injected():
    session = make_session()
    proc, context = make_processor(session)

    await proc._handle_candidate_turn("Hello")

    # q1 should now be IN_PROGRESS
    assert session.question_states["q1"].status == GoalStatus.IN_PROGRESS
    print("✓ opening question injected on first turn")


async def test_sufficient_answer_advances():
    session = make_session()
    proc, context = make_processor(session)

    # Simulate opening
    await proc._handle_candidate_turn("Hello")
    assert session.current_question.id == "q1"

    # Simulate sufficient answer
    good_answer = (
        "I tackled a distributed caching problem where Redis hot keys caused "
        "latency spikes. I profiled the system, identified the root cause, and "
        "implemented a local L1 cache with TTL. This was a complex task that "
        "required careful synchronization. The outcome was a 60 percent "
        "reduction in p99 latency across the entire cluster."
    )
    await proc._handle_candidate_turn(good_answer)
    assert session.question_states["q1"].status == GoalStatus.COVERED
    assert session.current_question.id == "q2"
    print("✓ sufficient answer advances to next question")


async def test_weak_answer_triggers_followup():
    session = make_session()
    proc, context = make_processor(session)

    await proc._handle_candidate_turn("Hello")
    await proc._handle_candidate_turn("I fixed some bugs.")  # too short

    assert session.question_states["q1"].follow_up_count == 1
    assert session.question_states["q1"].status == GoalStatus.IN_PROGRESS
    print("✓ weak answer triggers follow-up")


async def test_exhausted_followups_mark_weak():
    session = make_session()
    session.config.max_follow_ups_per_question = 1
    proc, context = make_processor(session)

    await proc._handle_candidate_turn("Hello")
    await proc._handle_candidate_turn("Short.")       # follow-up 1
    await proc._handle_candidate_turn("Still short.") # budget exhausted

    assert session.question_states["q1"].status == GoalStatus.WEAK
    assert session.current_question.id == "q2"
    print("✓ exhausted follow-ups marks weak and advances")


async def test_interview_completes():
    session = make_session()
    session.config.max_follow_ups_per_question = 0  # skip follow-ups
    proc, context = make_processor(session)

    good = (
        "I tackled a distributed caching problem with Redis hot keys causing "
        "latency spikes. Profiled, identified root cause, implemented L1 cache. "
        "Outcome was 60 percent reduction in p99 latency across the system."
    )

    await proc._handle_candidate_turn("Hello")
    await proc._handle_candidate_turn(good)  # q1 covered
    await proc._handle_candidate_turn(good)  # q2 covered

    assert session.status == InterviewStatus.COMPLETED
    print("✓ interview completes when all questions answered")


if __name__ == "__main__":
    # Sync tests
    test_word_count()
    test_filler_ratio()
    test_answer_sufficient_long()
    test_answer_insufficient_short()
    test_answer_insufficient_filler()

    # Async tests
    asyncio.run(test_opening_question_injected())
    asyncio.run(test_sufficient_answer_advances())
    asyncio.run(test_weak_answer_triggers_followup())
    asyncio.run(test_exhausted_followups_mark_weak())
    asyncio.run(test_interview_completes())

    print("\n✅ All tests passed — Phase 1 complete")
