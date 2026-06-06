"""
Working Pipeline Configuration for Pipecat Voice Agent
This module provides a properly ordered pipeline that handles transcripts, metrics, and audio correctly.
"""

import os
from loguru import logger
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker, PipelineParams
from pipecat.processors.aggregators.llm_response import LLMFullResponseAggregator
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import SpeechTimeoutUserTurnStopStrategy

from bot import create_interview_session
from transcript_accumulator import TranscriptAccumulator
from question_flow_processor import QuestionFlowProcessor
from events.broadcaster import broadcaster


class ImprovedResponseParser:
    """
    Improved parser that handles both streaming text and aggregated responses
    """
    from pipecat.frames.frames import Frame, TextFrame, LLMFullResponseEndFrame
    from pipecat.processors.frame_processor import FrameProcessor
    import json
    import re

    class Parser(FrameProcessor):
        def __init__(self, session, broadcaster):
            super().__init__()
            self._session = session
            self._broadcaster = broadcaster
            self._buffer = []
            self._response_started = False

        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)

            # Handle streaming text frames from LLM
            if isinstance(frame, TextFrame) and not self._response_started:
                # This is text coming from LLM
                self._buffer.append(frame.text)
                # Don't consume the frame, let it go to TTS
                await self.push_frame(frame, direction)
                return

            # Handle the aggregated response end frame
            elif isinstance(frame, LLMFullResponseEndFrame):
                logger.info("[ImprovedParser] Processing LLMFullResponseEndFrame")

                # Get full text from aggregator or buffer
                full_text = getattr(frame, 'text', '')
                if not full_text and self._buffer:
                    full_text = ''.join(self._buffer)

                self._buffer = []
                self._response_started = False

                if full_text:
                    # Try to extract JSON for evaluation
                    try:
                        json_match = re.search(r'(\{.*\})', full_text, re.DOTALL)
                        if json_match:
                            data = json.loads(json_match.group(1))
                            response_text = data.get("response", full_text)
                            evaluation = data.get("evaluation", {})

                            if evaluation:
                                self._session.add_evaluation(evaluation)
                                await self._broadcaster.broadcast("evaluation", {
                                    "session_id": self._session.session_id,
                                    "data": evaluation
                                })
                        else:
                            response_text = full_text
                    except:
                        response_text = full_text

                    # Add agent transcript
                    logger.info(f"[ImprovedParser] Agent transcript: {response_text[:100]}...")
                    self._session.add_turn(
                        speaker="agent",
                        text=response_text,
                        question_id=self._session.current_question.id if self._session.current_question else None
                    )

                    # Broadcast agent transcript
                    await self._broadcaster.broadcast("transcript", {
                        "speaker": "agent",
                        "text": response_text
                    })

                # Pass frame through for metrics
                await self.push_frame(frame, direction)
            else:
                # Pass all other frames through
                await self.push_frame(frame, direction)

    return Parser(session, broadcaster)


class ImprovedMetricsTracker:
    """
    Improved metrics tracker with better logging
    """
    from pipecat.frames.frames import Frame, LLMFullResponseEndFrame
    from pipecat.processors.frame_processor import FrameProcessor

    class Tracker(FrameProcessor):
        def __init__(self, session, broadcaster):
            super().__init__()
            self._session = session
            self._broadcaster = broadcaster
            self._total_tokens = 0

        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)

            if isinstance(frame, LLMFullResponseEndFrame):
                logger.info("[ImprovedMetrics] LLMFullResponseEndFrame received")

                # Check for usage data
                usage = getattr(frame, 'usage', None)
                if usage:
                    prompt_tokens = getattr(usage, 'prompt_tokens', 0)
                    completion_tokens = getattr(usage, 'completion_tokens', 0)
                    total_tokens = getattr(usage, 'total_tokens', 0)

                    self._total_tokens += total_tokens

                    logger.info(f"[ImprovedMetrics] Tokens - Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}")
                    logger.info(f"[ImprovedMetrics] Session total: {self._total_tokens}")

                    # Broadcast metrics
                    metrics_data = {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens
                    }

                    await self._broadcaster.broadcast("metrics", {
                        "session_id": self._session.session_id,
                        "metrics": metrics_data,
                        "session_total": self._total_tokens
                    })
                else:
                    logger.warning("[ImprovedMetrics] No usage data in frame!")

            await self.push_frame(frame, direction)

    return Tracker(session, broadcaster)


def create_working_pipeline(transport, stt, llm, tts):
    """
    Creates a properly ordered pipeline with all components working correctly
    """

    # Create session and context
    session = create_interview_session()
    session.start()

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            user_turn_strategies=UserTurnStrategies(
                stop=[SpeechTimeoutUserTurnStopStrategy()]
            )
        ),
    )

    # Create processors
    transcript_accumulator = TranscriptAccumulator(session, broadcaster)
    question_flow = QuestionFlowProcessor(session, context)
    response_parser = ImprovedResponseParser(session, broadcaster)
    metrics_tracker = ImprovedMetricsTracker(session, broadcaster)

    logger.info("[WorkingPipeline] Creating pipeline with proper order")

    # CRITICAL: Correct pipeline order
    # 1. Input from transport
    # 2. STT processes audio to text
    # 3. Transcript accumulator records user speech
    # 4. User aggregator collects for LLM context
    # 5. Question flow manages interview state
    # 6. LLM generates response
    # 7. Full response aggregator collects all LLM output (WITH usage metrics)
    # 8. Response parser extracts text and broadcasts transcripts
    # 9. Metrics tracker processes usage data
    # 10. TTS converts text to speech
    # 11. Output to transport
    # 12. Assistant aggregator maintains context

    pipeline = Pipeline([
        transport.input(),              # 1
        stt,                           # 2
        transcript_accumulator,        # 3
        user_aggregator,               # 4
        question_flow,                 # 5
        llm,                          # 6
        LLMFullResponseAggregator(),  # 7 - This creates the LLMFullResponseEndFrame with usage
        response_parser,               # 8 - Parse and broadcast transcripts
        metrics_tracker,               # 9 - Process metrics from aggregated frame
        tts,                          # 10
        transport.output(),           # 11
        assistant_aggregator,         # 12
    ])

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
            send_initial_empty_metrics=False,
        ),
    )

    return worker, session