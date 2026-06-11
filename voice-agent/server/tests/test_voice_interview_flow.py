# test_voice_interview_flow.py
#
# Integration test for the LIVE voice-interview path WITHOUT real Deepgram/Cartesia/
# OpenAI keys or a WebRTC/browser session.
#
# The real pipeline is:  mic → Deepgram STT → QuestionFlowProcessor → OpenAI LLM →
# Cartesia TTS → speaker. STT emits a `TranscriptionFrame` for each candidate
# utterance; the flow processor consumes it, advances the interview, and pushes an
# `LLMRunFrame` downstream — the cue that makes the LLM generate the next line and
# the TTS speak it. By feeding TranscriptionFrames straight into `process_frame`
# and capturing the frames pushed downstream, we exercise that exact STT→flow→
# LLM/TTS seam offline. (Pure flow *logic* is covered by test_question_flow.py;
# this covers the frame-dispatch integration that the live call depends on.)

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from pipecat.frames.frames import LLMRunFrame, TranscriptionFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection

import processors.question_flow_processor as qfp
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

# Long, specific answers the heuristic evaluator accepts as "sufficient". The
# evaluator weighs theme overlap, so each answer is written to match its question's
# expected_theme (q1 = "problem solution outcome", q2 = "team communication resolution").
GOOD_ANSWER = (
    "I tackled a distributed caching problem where Redis hot keys caused latency "
    "spikes. I profiled the system, found the root cause, and implemented a local "
    "L1 cache with TTL. The outcome was a 60 percent reduction in p99 latency "
    "across the whole cluster, and it shipped to production within a week."
)
GOOD_ANSWER_Q2 = (
    "When two engineers on my team disagreed about an API design, I focused on "
    "clear communication: I set up a short meeting where each explained their "
    "reasoning, I listened to both sides, and we found the shared goal. The team "
    "agreed on a compromise interface and the conflict was resolved without any "
    "lingering tension, which kept the whole team aligned and productive."
)


def _config(max_follow_ups=2):
    return RecruiterConfig(
        job_role="Backend Engineer", company_name="Acme", interview_type="technical",
        system_prompt="You are an interviewer.",
        max_follow_ups_per_question=max_follow_ups,
        questions=[
            InterviewQuestion(id="q1", text="Describe a hard problem you solved.",
                              goal_id="g1", expected_depth=AnswerDepth.LONG,
                              expected_theme="problem solution outcome",
                              follow_ups=[FollowUpPrompt("Can you be more specific?", "too vague")]),
            InterviewQuestion(id="q2", text="How do you handle team conflict?",
                              goal_id="g2", expected_depth=AnswerDepth.MEDIUM,
                              expected_theme="team communication resolution"),
        ],
        goals=[
            InterviewGoal("g1", "Problem Solving", "...", 0.6),
            InterviewGoal("g2", "Communication", "...", 0.4),
        ],
    )


@pytest_asyncio.fixture
async def interview():
    """A started session + flow processor with the live external services stubbed:
    push_frame captures downstream frames (LLM/TTS cues), the SSE broadcaster and the
    DB persist are mocked so the test is fully offline."""
    session = InterviewSession(candidate_id="c1", candidate_name="Test", config=_config())
    session.start()
    context = LLMContext()
    proc = qfp.QuestionFlowProcessor(session, context)
    proc.push_frame = AsyncMock()
    with patch.object(qfp.broadcaster, "broadcast", AsyncMock()), \
         patch("database.db_manager.save_session_progress", AsyncMock()):
        yield session, proc, context


async def _stt_says(proc, text):
    """Simulate Deepgram emitting a finalized transcription for a candidate utterance."""
    frame = TranscriptionFrame(text=text, user_id="candidate", timestamp="2024-01-01T00:00:00Z")
    await proc.process_frame(frame, FrameDirection.DOWNSTREAM)


def _pushed(proc):
    return [type(c.args[0]).__name__ for c in proc.push_frame.call_args_list]


def _agent_was_cued_to_speak(proc):
    """An LLMRunFrame downstream is what drives the LLM→TTS to actually speak."""
    return any(isinstance(c.args[0], LLMRunFrame) for c in proc.push_frame.call_args_list)


# ── The STT→flow→LLM/TTS seam ───────────────────────────────────────────────────

async def test_first_transcription_opens_interview_and_cues_speech(interview):
    session, proc, context = interview

    await _stt_says(proc, "Hello, I'm ready.")

    # The first utterance triggers the opening question...
    assert proc._opening_done is True
    assert session.question_states["q1"].status == GoalStatus.IN_PROGRESS
    # ...the agent is cued to speak (LLM generate → TTS), and the opening
    # instruction is queued in the LLM context that the (mocked) LLM would render.
    assert _agent_was_cued_to_speak(proc)
    assert any(m["role"] == "system" for m in context.get_messages())


async def test_transcription_frame_is_passed_through(interview):
    """The processor must forward the STT frame downstream so the rest of the
    pipeline (aggregators/transport) keeps flowing — not swallow it."""
    session, proc, context = interview
    await _stt_says(proc, "Hello")
    assert "TranscriptionFrame" in _pushed(proc)


async def test_scripted_interview_runs_to_completion(interview):
    session, proc, context = interview

    await _stt_says(proc, "Hi, ready to start.")   # opening → asks q1
    assert session.current_question.id == "q1"

    await _stt_says(proc, GOOD_ANSWER)             # q1 sufficient → advance, ask q2
    assert session.question_states["q1"].status == GoalStatus.COVERED
    assert session.current_question.id == "q2"

    await _stt_says(proc, GOOD_ANSWER_Q2)          # q2 sufficient → complete + close
    assert session.question_states["q2"].status == GoalStatus.COVERED
    assert session.status == InterviewStatus.COMPLETED

    # The agent was cued to speak on every step (opening + 2 asks/close all emit
    # LLMRunFrames), and the persisted progress was written as the candidate advanced.
    llm_runs = _pushed(proc).count("LLMRunFrame")
    assert llm_runs >= 3


async def test_weak_answer_triggers_followup_not_advance(interview):
    session, proc, context = interview

    await _stt_says(proc, "Hello")            # opening → q1
    await _stt_says(proc, "I fixed a bug.")   # too short → follow-up, stay on q1

    assert session.question_states["q1"].follow_up_count == 1
    assert session.question_states["q1"].status == GoalStatus.IN_PROGRESS
    assert session.current_question.id == "q1"
    assert _agent_was_cued_to_speak(proc)     # follow-up still cues the agent to speak


async def test_empty_transcription_is_ignored_but_forwarded(interview):
    """Deepgram occasionally emits empty/whitespace finals — they must not advance
    the interview, but must still flow through the pipeline."""
    session, proc, context = interview

    await _stt_says(proc, "   ")

    assert proc._opening_done is False                       # no turn was processed
    assert session.question_states["q1"].status == GoalStatus.PENDING
    assert not _agent_was_cued_to_speak(proc)                # agent not asked to speak
    assert "TranscriptionFrame" in _pushed(proc)             # but frame still forwarded


async def test_flow_runs_with_no_real_services(interview):
    """Guard: the whole interview turn is driven purely by frames + the LLM context.
    Nothing here imports or calls Deepgram/Cartesia/OpenAI — proving the live path is
    exercisable in CI without keys or a WebRTC session."""
    session, proc, context = interview
    await _stt_says(proc, "Hi.")
    await _stt_says(proc, GOOD_ANSWER)
    # The lines the TTS would speak are the instructions accumulated in context;
    # they exist without any model call having happened.
    system_msgs = [m for m in context.get_messages() if m["role"] == "system"]
    assert len(system_msgs) >= 2
