# bot.py

import os
import sys

from dotenv import load_dotenv
from loguru import logger

# No local VAD needed (using transport VAD)
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.aggregators.llm_response import LLMFullResponseAggregator
from core.metrics import MetricsTracker
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import SpeechTimeoutUserTurnStopStrategy
from pipecat.runner.types import (
    RunnerArguments,
    LiveKitRunnerArguments,
)
from pipecat.services.cartesia.tts import CartesiaHttpTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.livekit.transport import LiveKitTransport
from pipecat.workers.runner import WorkerRunner

from interview_session import (
    InterviewSession, RecruiterConfig, InterviewQuestion,
    InterviewGoal, FollowUpPrompt, AnswerDepth
)
from processors.transcript_accumulator import TranscriptAccumulator
from processors.question_flow_processor import QuestionFlowProcessor
from fixed_json_parser import FixedLLMResponseParser
from events.broadcaster import broadcaster

load_dotenv(override=True)

try:
    logger.remove(0)
except Exception:
    pass
logger.add(sys.stderr, level="DEBUG")

def create_interview_session() -> InterviewSession:
    """Creates a default interview session for testing."""
    config = RecruiterConfig(
        job_role="Backend Engineer",
        company_name="Acme Corp",
        interview_type="technical",
        system_prompt=(
            "You are a professional, warm AI interviewer conducting a technical interview. "
            "Speak naturally and conversationally like you're having a friendly professional conversation. "
            "Ask thoughtful follow-up questions based on what the candidate tells you. "
            "Keep your responses concise and engaging. Never use bullet points or lists. "
            "Focus on understanding the candidate's experience and technical background."
        ),
        time_limit_seconds=1800,
        max_follow_ups_per_question=2,
        questions=[
            InterviewQuestion(
                id="q1",
                text="Can you tell me about a technically challenging problem you solved recently?",
                goal_id="problem_solving",
                expected_depth=AnswerDepth.LONG,
                expected_theme="problem solution outcome approach",
                follow_ups=[
                    FollowUpPrompt(
                        text="Could you walk me through your specific approach step by step?",
                        trigger_reason="answer too vague or too short",
                    ),
                    FollowUpPrompt(
                        text="What was the measurable outcome of your solution?",
                        trigger_reason="no concrete outcome mentioned",
                    ),
                ],
            ),
            InterviewQuestion(
                id="q2",
                text="How do you approach working in a team when there are disagreements?",
                goal_id="communication",
                expected_depth=AnswerDepth.MEDIUM,
                expected_theme="team communication conflict resolution",
                follow_ups=[
                    FollowUpPrompt(
                        text="Can you give me a specific example from your experience?",
                        trigger_reason="answer too abstract, no example given",
                    ),
                ],
            ),
        ],
        goals=[
            InterviewGoal(
                id="problem_solving",
                label="Problem Solving",
                description="Structured thinking through technical challenges",
                weight=0.6,
            ),
            InterviewGoal(
                id="communication",
                label="Communication",
                description="Clear communication and conflict handling",
                weight=0.4,
            ),
        ],
    )
    return InterviewSession(
        candidate_id="cand_001",
        candidate_name="Test Candidate",
        config=config,
    )


# --- Generic, per-job session building (used by the real runner.py flow) ---

BASE_INTERVIEWER_PERSONA = (
    "You are a professional, warm AI interviewer conducting a {interview_type} interview "
    "for the role of {job_role} at {company_name}. Speak naturally and conversationally, "
    "like a friendly professional. Ask thoughtful follow-up questions based on what the "
    "candidate tells you. Keep your responses concise and engaging. Never use bullet points "
    "or lists. Focus on assessing the candidate against the role's goals."
)


def compose_system_prompt(
    job_role: str,
    company_name: str,
    interview_type: str = "technical",
    job_llm_prompt: str | None = None,
) -> str:
    """Build the interviewer system prompt for a specific job/role."""
    prompt = BASE_INTERVIEWER_PERSONA.format(
        interview_type=interview_type or "technical",
        job_role=job_role or "this role",
        company_name=company_name or "the company",
    )
    if job_llm_prompt:
        prompt += "\n\nRole-specific evaluation guidance:\n" + job_llm_prompt.strip()
    return prompt


def build_interview_session(
    *,
    candidate_id: int | str,
    candidate_name: str | None,
    config: RecruiterConfig,
    job_id: int | None = None,
    session_id: str | None = None,
) -> InterviewSession:
    """Assemble an InterviewSession for a specific candidate from a prepared config.

    candidate_id / job_id are carried for DB linkage (interview_sessions.candidate_id/job_id).
    A caller-supplied ``session_id`` makes the session deterministic per interview link, so
    re-opening the same link resumes the SAME session row instead of creating a new one;
    when omitted, a random UUID is used.
    """
    kwargs = {"session_id": session_id} if session_id else {}
    session = InterviewSession(
        candidate_id=str(candidate_id),
        candidate_name=candidate_name or "Candidate",
        config=config,
        **kwargs,
    )
    # Carry the numeric DB ids for linkage (read defensively elsewhere).
    session.db_candidate_id = int(candidate_id) if str(candidate_id).isdigit() else None
    session.db_job_id = job_id
    return session


async def run_bot(transport: BaseTransport):
    """Main bot logic."""
    logger.info("Starting Interview Bot")

    session = create_interview_session()
    session.start()

    # Speech-to-Text service
    stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))

    # Text-to-Speech service
    tts = CartesiaHttpTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        voice_id=os.getenv("CARTESIA_VOICE_ID", "71a7ad14-091c-4e8e-a314-022ece01c121"),
    )

    # LLM service
    llm = GroqLLMService(
        api_key=os.getenv("GROQ_API_KEY"),
        settings=GroqLLMService.Settings(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            system_instruction=session.config.system_prompt,
        ),
    )

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            user_turn_strategies=UserTurnStrategies(
                stop=[SpeechTimeoutUserTurnStopStrategy()]
            )
        ),
    )

    # Phase 1 processors
    transcript_accumulator = TranscriptAccumulator(session, broadcaster)
    question_flow = QuestionFlowProcessor(session, context)
    response_parser = FixedLLMResponseParser(session, broadcaster)
    metrics_tracker = MetricsTracker(session, broadcaster)

    # Pipeline - assembled from reusable components
    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            transcript_accumulator,
            user_aggregator,
            question_flow,
            llm,
            response_parser,
            LLMFullResponseAggregator(),
            metrics_tracker,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        observers=[],
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"Candidate connected — session {session.session_id}")
        session.log_connection_event("joined")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info(f"Candidate disconnected — session {session.session_id}")
        session.log_connection_event("dropped")
        await worker.cancel()

    runner = WorkerRunner(handle_sigint=False)

    await runner.add_workers(worker)
    await runner.run()


async def bot(runner_args: RunnerArguments):
    """Main bot entry point."""

    transport = None

    match runner_args:
        case LiveKitRunnerArguments():
            transport = LiveKitTransport(
                url=runner_args.url,
                token=runner_args.token,
                room_name=runner_args.room_name,
                params=TransportParams(
                    audio_in_enabled=True,
                    audio_out_enabled=True,
                ),
            )
        case _:
            logger.error(f"Unsupported runner arguments type: {type(runner_args)}")
            return

    await run_bot(transport)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
