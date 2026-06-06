"""
Dual-mode Bot Manager - Supports both Single LLM and Dual LLM (Judge + Responder) pipelines
"""

import os
from loguru import logger
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.frames.frames import LLMRunFrame
from working_processors import WorkingTranscriptProcessor, WorkingMetricsProcessor
from judge_processor import JudgeProcessor, DualLLMContextProcessor
from bot import create_interview_session


class BotManager:
    """
    Manages bot pipeline with support for two modes:
    1. Single LLM - Traditional pipeline
    2. Dual LLM - Judge evaluates, Responder uses evaluation context
    """

    def __init__(self, transport, stt, llm, tts, context, user_aggregator, assistant_aggregator, mode="single"):
        """
        Initialize bot manager with specified pipeline mode

        Args:
            mode: "single" for traditional pipeline, "dual" for judge+responder pipeline
        """
        self.transport = transport
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.context = context
        self.user_aggregator = user_aggregator
        self.assistant_aggregator = assistant_aggregator
        self.mode = mode

        # Create session
        from bot import create_interview_session
        from events.broadcaster import broadcaster
        self.session = create_interview_session()
        self.broadcaster = broadcaster

        # Create processors
        self.transcript_processor = WorkingTranscriptProcessor(self.session, self.broadcaster)
        self.metrics_processor = WorkingMetricsProcessor(self.session, self.broadcaster)

        # Create pipeline based on mode
        if mode == "dual":
            logger.info("[BotManager] Initializing DUAL LLM pipeline (Judge + Responder)")
            self.pipeline = self._create_dual_pipeline()
        else:
            logger.info("[BotManager] Initializing SINGLE LLM pipeline")
            self.pipeline = self._create_single_pipeline()

        # Create worker
        self.worker = PipelineWorker(
            self.pipeline,
            params=PipelineParams(
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
        )

    def _create_single_pipeline(self):
        """Create traditional single LLM pipeline"""
        return Pipeline([
            self.transport.input(),
            self.stt,
            self.transcript_processor,
            self.user_aggregator,
            self.llm,
            self.metrics_processor,
            self.tts,
            self.transport.output(),
            self.assistant_aggregator,
        ])

    def _create_dual_pipeline(self):
        """Create dual LLM pipeline with judge and context-aware responder"""

        # Create judge processor
        api_key = os.getenv("GROQ_API_KEY")
        self.judge_processor = JudgeProcessor(self.session, self.broadcaster, api_key)

        # Create context enrichment processor
        self.context_processor = DualLLMContextProcessor(self.session, self.context)

        return Pipeline([
            self.transport.input(),
            self.stt,
            self.transcript_processor,
            # Judge evaluates in parallel (non-blocking)
            self.judge_processor,
            self.user_aggregator,
            # Context processor adds evaluation to LLM messages
            self.context_processor,
            self.llm,
            self.metrics_processor,
            self.tts,
            self.transport.output(),
            self.assistant_aggregator,
        ])

    async def start(self):
        """Start the interview session"""
        self.session.start()

        # Log pipeline mode
        await self.broadcaster.broadcast("pipeline_mode", {
            "mode": self.mode,
            "description": "Dual LLM (Judge + Responder)" if self.mode == "dual" else "Single LLM"
        })

        logger.info(f"[BotManager] Session started - Mode: {self.mode}, ID: {self.session.session_id}")

        # Queue initial LLM frame to start the conversation
        await self.pipeline.push_frame(LLMRunFrame())

    async def inject_text(self, text: str):
        """Inject text manually from dashboard"""
        from pipecat.frames.frames import TextFrame
        frame = TextFrame(text=text)
        await self.pipeline.push_frame(frame)

    def get_pipeline_info(self):
        """Get current pipeline configuration"""
        return {
            "mode": self.mode,
            "has_judge": self.mode == "dual",
            "judge_model": "llama-3.1-8b-instant" if self.mode == "dual" else None,
            "responder_model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            "session_id": self.session.session_id
        }