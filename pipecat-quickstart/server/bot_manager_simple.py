import asyncio
import os
from loguru import logger
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker, PipelineParams
from pipecat.frames.frames import StartFrame, TranscriptionFrame
from bot import create_interview_session
from events.broadcaster import broadcaster


class BotManager:
    def __init__(self, transport, stt, llm, tts, context, user_aggregator, assistant_aggregator):
        """
        Simple bot manager that creates a working pipeline
        """
        self.transport = transport
        self.session = create_interview_session()
        self.session.start()
        self.session.auto_kill_on_disconnect = False

        logger.info("[BotManager] Initializing components...")

        # Import processors here to avoid circular imports
        from simple_processors import (
            SimpleTranscriptAccumulator,
            SimpleQuestionFlow,
            SimpleLLMResponseHandler,
            SimpleMetricsTracker
        )

        # Create simple processors
        transcript_accumulator = SimpleTranscriptAccumulator(self.session, broadcaster)
        self.question_flow = SimpleQuestionFlow(self.session, context)
        response_handler = SimpleLLMResponseHandler(self.session, broadcaster)
        metrics_tracker = SimpleMetricsTracker(self.session, broadcaster)

        logger.info("[BotManager] Building pipeline...")

        # Build a simple, working pipeline
        # Based on local_bot.py structure with added processors
        self.pipeline = Pipeline([
            self.transport.input(),      # Audio input
            stt,                         # Speech to text
            transcript_accumulator,      # Record user transcript
            user_aggregator,            # Aggregate user context
            self.question_flow,         # Manage interview flow
            llm,                        # Generate response
            response_handler,           # Handle LLM response & broadcast
            metrics_tracker,            # Track metrics
            tts,                        # Text to speech
            self.transport.output(),    # Audio output
            assistant_aggregator,       # Aggregate assistant context
        ])

        self.worker = PipelineWorker(
            self.pipeline,
            params=PipelineParams(
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
        )

        logger.info("[BotManager] Pipeline created successfully")

    async def start(self):
        """Start the bot session"""
        logger.info(f"[BotManager] Session {self.session.session_id} started")
        # Worker handles the actual start

    async def inject_text(self, text, user_id="candidate"):
        """Inject text into the pipeline"""
        frame = TranscriptionFrame(text=text, user_id=user_id, timestamp="100")
        logger.info(f"[BotManager] Injecting text: {text}")
        await self.transport.input().push_frame(frame)