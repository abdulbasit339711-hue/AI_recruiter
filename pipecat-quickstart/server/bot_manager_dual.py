"""
Dual-mode Bot Manager - Supports both Single LLM and Dual LLM (Judge + Responder) pipelines
"""

import os
import wave
from loguru import logger
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.frames.frames import LLMRunFrame
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from working_processors import WorkingTranscriptProcessor, WorkingMetricsProcessor
from judge_processor import JudgeProcessor, DualLLMContextProcessor
from bot import create_interview_session
from services.goal_tracking_service import GoalTrackingService
from processors.goal_tracking_processor import GoalTrackingProcessor, GoalAwareTranscriptProcessor
from database import initialize_database


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

        # The interview session is configured per-candidate at connect time via
        # configure_session(); processors are built session-less and updated then.
        from events.broadcaster import broadcaster
        self.session = None
        self.broadcaster = broadcaster

        # Initialize goal tracking service (session attached later)
        self.goal_service = None
        self.goal_processor = None
        if os.getenv("GOAL_TRACKING_ENABLED", "true").lower() == "true":
            groq_api_key = os.getenv("GROQ_API_KEY")
            if groq_api_key:
                self.goal_service = GoalTrackingService(groq_api_key)
                self.goal_processor = GoalTrackingProcessor(
                    None, self.goal_service, self.broadcaster, groq_api_key
                )
                # Use goal-aware transcript processor
                self.transcript_processor = GoalAwareTranscriptProcessor(
                    None, self.broadcaster, self.goal_service
                )
                logger.info("[BotManager] Goal tracking enabled")
            else:
                logger.warning("[BotManager] Goal tracking disabled - no GROQ_API_KEY")
                self.transcript_processor = WorkingTranscriptProcessor(None, self.broadcaster)
        else:
            logger.info("[BotManager] Goal tracking disabled")
            self.transcript_processor = WorkingTranscriptProcessor(None, self.broadcaster)

        # Create metrics processor
        self.metrics_processor = WorkingMetricsProcessor(None, self.broadcaster)

        # Audio recording: one mono buffer mixing candidate + bot audio. Flushed to a
        # WAV on the shared recordings dir at finalize so HR can replay the interview.
        self.audio_buffer = AudioBufferProcessor(num_channels=1)
        self._recorded_audio: bytes | None = None
        self._audio_sample_rate: int = 0

        @self.audio_buffer.event_handler("on_audio_data")
        async def _on_audio_data(buffer, audio, sample_rate, num_channels):
            # Fired on stop_recording() / EndFrame with the full merged recording.
            self._recorded_audio = audio
            self._audio_sample_rate = sample_rate

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
        pipeline_processors = [
            self.transport.input(),
            self.stt,
            self.transcript_processor,
        ]

        # Add goal tracking if enabled
        if self.goal_processor:
            pipeline_processors.append(self.goal_processor)

        pipeline_processors.extend([
            self.user_aggregator,
            self.llm,
            self.metrics_processor,
            self.tts,
            self.audio_buffer,
            self.transport.output(),
            self.assistant_aggregator,
        ])

        return Pipeline(pipeline_processors)

    def _create_dual_pipeline(self):
        """Create dual LLM pipeline with judge and context-aware responder"""

        # Create judge processor
        api_key = os.getenv("GROQ_API_KEY")
        self.judge_processor = JudgeProcessor(self.session, self.broadcaster, api_key)

        # Create context enrichment processor
        self.context_processor = DualLLMContextProcessor(self.session, self.context)

        pipeline_processors = [
            self.transport.input(),
            self.stt,
            self.transcript_processor,
            # Judge evaluates in parallel (non-blocking)
            self.judge_processor,
        ]

        # Add goal tracking if enabled (after judge for context)
        if self.goal_processor:
            pipeline_processors.append(self.goal_processor)

        pipeline_processors.extend([
            self.user_aggregator,
            # Context processor adds evaluation to LLM messages
            self.context_processor,
            self.llm,
            self.metrics_processor,
            self.tts,
            self.audio_buffer,
            self.transport.output(),
            self.assistant_aggregator,
        ])

        return Pipeline(pipeline_processors)

    async def start(self):
        """Start the interview session"""
        # Initialize database connection if goal tracking is enabled
        if self.goal_service:
            try:
                await initialize_database()
                logger.info("[BotManager] Database initialized for goal tracking")
            except Exception as e:
                logger.error(f"[BotManager] Failed to initialize database: {e}")
                # Continue without database support

        # Log pipeline mode (the interview session itself is attached later via
        # configure_session() when a candidate connects).
        await self.broadcaster.broadcast("pipeline_mode", {
            "mode": self.mode,
            "description": "Dual LLM (Judge + Responder)" if self.mode == "dual" else "Single LLM"
        })

        logger.info(f"[BotManager] Worker started - Mode: {self.mode} (awaiting interview config)")

    def _session_processors(self):
        """All pipeline processors that need the per-interview session."""
        procs = [self.transcript_processor, self.metrics_processor]
        if self.goal_processor:
            procs.append(self.goal_processor)
        for attr in ("judge_processor", "context_processor"):
            p = getattr(self, attr, None)
            if p is not None:
                procs.append(p)
        return procs

    async def configure_session(self, session) -> None:
        """Attach a per-interview session to the running pipeline (single concurrency).

        Sets the session on every processor, seeds the LLM context with the
        role-specific system prompt, and creates the DB session row + goals.
        """
        self.session = session
        for p in self._session_processors():
            if hasattr(p, "set_session"):
                p.set_session(session)

        # Per-session system prompt (LLM service is built config-free).
        try:
            self.context.add_message(
                {"role": "system", "content": session.config.system_prompt}
            )
        except Exception as e:
            logger.warning(f"[BotManager] Could not seed system prompt into context: {e}")

        session.start()

        # Begin audio capture for this interview (resets buffers, sets recording on).
        try:
            await self.audio_buffer.start_recording()
        except Exception as e:
            logger.warning(f"[BotManager] Could not start audio recording: {e}")

        # Create the interview_sessions row + session goals up front (idempotent).
        if self.goal_processor:
            try:
                await self.goal_processor.initialize_goals()
            except Exception as e:
                logger.error(f"[BotManager] Goal initialization failed: {e}")

        logger.info(
            f"[BotManager] Configured interview {session.session_id} "
            f"(role='{session.config.job_role}', candidate='{session.candidate_name}')"
        )

    async def inject_text(self, text: str):
        """Inject text manually from dashboard"""
        logger.info(f"[BotManager] Injecting manual text: {text}")

        # Send as transcription frame to mimic STT output
        # This will go through the transcript processor and aggregator
        from pipecat.frames.frames import TranscriptionFrame
        import time
        frame = TranscriptionFrame(
            text=text,
            user_id="manual-input",
            timestamp=str(time.time())
        )
        # Push to transport input so it flows through the pipeline properly
        await self.transport.input().push_frame(frame)

    def get_pipeline_info(self):
        """Get current pipeline configuration"""
        return {
            "mode": self.mode,
            "has_judge": self.mode == "dual",
            "judge_model": "llama-3.1-8b-instant" if self.mode == "dual" else None,
            "responder_model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            "session_id": self.session.session_id if self.session else None,
            "goal_tracking_enabled": self.goal_service is not None
        }

    async def get_goal_progress(self):
        """Get current goal progress summary"""
        if not self.goal_service:
            return {"error": "Goal tracking not enabled"}

        try:
            return await self.goal_service.get_goal_progress_summary(self.session.session_id)
        except Exception as e:
            logger.error(f"[BotManager] Failed to get goal progress: {e}")
            return {"error": str(e)}

    async def get_adaptive_question_suggestion(self):
        """Get adaptive question suggestion based on goal progress"""
        if not self.goal_processor:
            return None

        try:
            return await self.goal_processor.get_adaptive_question_suggestion()
        except Exception as e:
            logger.error(f"[BotManager] Failed to get question suggestion: {e}")
            return None

    async def finalize_session(self):
        """Finalize this interview: run the final goal analysis and persist it.

        Called once when the bot's worker ends (see runner._make_and_run_bot).
        Note: the DB pool is a process-global shared by every concurrent bot and the
        HTTP API, so we must NOT close it here — that is owned by process shutdown,
        not by a single interview ending.
        """
        if self.goal_processor:
            try:
                await self.goal_processor.finalize_session_goals()
                logger.info("[BotManager] Session goals finalized")
            except Exception as e:
                logger.error(f"[BotManager] Failed to finalize goals: {e}")

        # Persist the per-service token breakdown (STT/LLM-in/LLM-out/TTS).
        if self.metrics_processor:
            try:
                await self.metrics_processor.persist_summary()
            except Exception as e:
                logger.error(f"[BotManager] Failed to persist token summary: {e}")

        # Flush + persist the interview audio recording.
        await self._save_recording()

        sid = self.session.session_id if self.session else "?"
        logger.info(f"[BotManager] Session finalized: {sid}")

    async def _save_recording(self) -> None:
        """Stop recording, write the merged WAV, and store its path on the session row."""
        if not self.session:
            return
        try:
            # EndFrame usually stops recording already (firing on_audio_data); calling
            # again is a no-op once recording is off. This covers the cancel path too.
            await self.audio_buffer.stop_recording()
        except Exception as e:
            logger.warning(f"[BotManager] stop_recording failed: {e}")

        if not self._recorded_audio:
            logger.info("[BotManager] No audio captured; skipping recording save")
            return

        recordings_dir = os.getenv("RECORDINGS_DIR", "/mnt/muaaz/AI_recruiter/data/recordings")
        try:
            os.makedirs(recordings_dir, exist_ok=True)
            path = os.path.join(recordings_dir, f"{self.session.session_id}.wav")
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit PCM
                wf.setframerate(self._audio_sample_rate or 16000)
                wf.writeframes(self._recorded_audio)
            from database import db_manager
            await db_manager.update_session_audio(self.session.session_id, path)
            logger.info(f"[BotManager] Saved interview audio: {path} ({len(self._recorded_audio)} bytes)")
        except Exception as e:
            logger.error(f"[BotManager] Failed to save interview audio: {e}")