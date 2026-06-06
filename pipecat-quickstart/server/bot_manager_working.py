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
        Clean working bot manager based on local_bot.py structure
        """
        logger.info("[BotManager] Initializing working bot manager")

        self.transport = transport
        self.session = create_interview_session()
        self.session.start()
        self.session.auto_kill_on_disconnect = False

        # Import processors here to avoid import issues
        from working_processors import (
            WorkingTranscriptProcessor,
            WorkingMetricsProcessor
        )

        # Create processors
        transcript_processor = WorkingTranscriptProcessor(self.session, broadcaster)
        metrics_processor = WorkingMetricsProcessor(self.session, broadcaster)

        logger.info("[BotManager] Building clean pipeline")

        # Clean pipeline based on working local_bot.py structure
        # We insert our processors at safe points without breaking the flow
        self.pipeline = Pipeline([
            self.transport.input(),        # Audio input
            stt,                          # Speech-to-text
            transcript_processor,         # Capture user transcripts
            user_aggregator,             # User context aggregation
            llm,                         # LLM generation
            metrics_processor,           # Capture metrics from LLM
            tts,                         # Text-to-speech
            self.transport.output(),     # Audio output
            assistant_aggregator,        # Assistant context aggregation
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
        logger.info(f"[BotManager] Starting session {self.session.session_id}")

    async def inject_text(self, text, user_id="candidate"):
        """Inject text into the pipeline"""
        frame = TranscriptionFrame(text=text, user_id=user_id, timestamp="100")
        logger.info(f"[BotManager] Injecting text: {text[:50]}...")
        await self.transport.input().push_frame(frame)