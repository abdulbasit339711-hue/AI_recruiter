"""
Dual-mode Bot Manager - Supports both Single LLM and Dual LLM (Judge + Responder) pipelines
"""

import asyncio
import threading
import os
import wave
from loguru import logger
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.frames.frames import LLMRunFrame
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.services.whisper.base_stt import BaseWhisperSTTService
from pipecat.frames.frames import AudioRawFrame, VADUserStartedSpeakingFrame, VADUserStoppedSpeakingFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import (
    SpeechTimeoutUserTurnStopStrategy,
)
from processors.transcript_metrics_processors import WorkingTranscriptProcessor, WorkingMetricsProcessor
from processors.judge_processor import JudgeProcessor, DualLLMContextProcessor
from bot import create_interview_session
from services.goal_tracking_service import GoalTrackingService
from processors.goal_tracking_processor import GoalTrackingProcessor, GoalAwareTranscriptProcessor
from database import initialize_database


class _AudioDebugProcessor(FrameProcessor):
    """Temporary: logs audio frame counts and VAD events to diagnose STT silence."""

    def __init__(self):
        super().__init__()
        self._audio_count = 0
        self._log_every = 50  # log every 50 audio frames (~1 s at 20 ms chunks)

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, AudioRawFrame):
            self._audio_count += 1
            if self._audio_count % self._log_every == 0:
                logger.debug(
                    f"[AudioDebug] {self._audio_count} audio frames received "
                    f"(sample_rate={frame.sample_rate}, len={len(frame.audio)})"
                )
        elif isinstance(frame, VADUserStartedSpeakingFrame):
            logger.info(f"[AudioDebug] VADUserStartedSpeakingFrame -> STT will buffer audio")
        elif isinstance(frame, VADUserStoppedSpeakingFrame):
            logger.info(f"[AudioDebug] VADUserStoppedSpeakingFrame -> STT will transcribe")
        elif isinstance(frame, TranscriptionFrame):
            logger.info(f"[AudioDebug] TranscriptionFrame: '{getattr(frame, 'text', '?')}'")
        await self.push_frame(frame, direction)


# ---------------------------------------------------------------------------
# Voice-activity / turn-taking configuration (single source of truth)
# ---------------------------------------------------------------------------
# In this stack the *transport* has no Silero VAD analyzer — Deepgram STT emits
# the VAD start/stop events (server-side VAD), and the candidate's turn is
# declared over by SpeechTimeoutUserTurnStopStrategy once the post-pause window
# elapses. So there are two explicit knobs, both env-overridable:
#
#   VAD_USER_SPEECH_TIMEOUT_SECS  — how long to keep listening after the
#       candidate pauses before we treat the turn as finished. Pipecat's
#       default (0.6s) is tuned for casual chat and cuts off interviewees
#       mid-thought. We default to 2.0s; raise toward 3.0s for very
#       deliberate candidates (cf. the Gemini coach's SILENCE_DURATION_MS=3000,
#       chosen precisely to "prevent constant interruption").
#
#   DEEPGRAM_ENDPOINTING_MS — silence (ms) Deepgram waits before finalizing a
#       transcript. Left unset (None) keeps Deepgram's own default. This is the
#       STT-side counterpart to the coach's prefix/endpoint padding; the bot's
#       first-word capture is handled by Deepgram's internal audio buffering,
#       so there is no separate PREFIX_PADDING knob to set here.
#
# Tuning the turn window here keeps both entrypoints (runner.py and bot.py)
# consistent instead of constructing a bare SpeechTimeoutUserTurnStopStrategy()
# in two places.

VAD_USER_SPEECH_TIMEOUT_SECS: float = float(
    os.getenv("VAD_USER_SPEECH_TIMEOUT_SECS", "2.0")
)

_DEEPGRAM_ENDPOINTING_MS_RAW = os.getenv("DEEPGRAM_ENDPOINTING_MS")
DEEPGRAM_ENDPOINTING_MS: int | None = (
    int(_DEEPGRAM_ENDPOINTING_MS_RAW) if _DEEPGRAM_ENDPOINTING_MS_RAW else None
)

# Record the candidate's camera (when they publish it) to a local MP4 alongside
# the audio WAV, so HR can replay the interview with picture. Requires the
# transport's video_in_enabled (runner.py reads this flag too). Best-effort:
# a missing camera, PyAV, or any encode error leaves the audio recording intact.
RECORD_VIDEO: bool = os.getenv("RECORD_VIDEO", "true").lower() in ("1", "true", "yes", "on")

# Analyze the candidate's video with a Groq vision model (~1 fps sampled, analyzed
# every VISION_ANALYZE_INTERVAL_SECS) for presence/engagement, integrity, a neutral
# per-interval summary, and advisory delivery notes. Best-effort and off the critical
# path; results are broadcast over SSE and written to a {session}.vision.json sidecar.
# ADVISORY ONLY — never auto-scored into the candidate result (see processor docstring).
ANALYZE_VIDEO: bool = os.getenv("ANALYZE_VIDEO", "true").lower() in ("1", "true", "yes", "on")


def build_user_turn_strategies() -> UserTurnStrategies:
    """Turn-taking strategy with an interview-appropriate silence window.

    The single place that decides how long a pause is allowed before the
    candidate's turn ends. Use this instead of instantiating
    SpeechTimeoutUserTurnStopStrategy() directly so the window stays in sync
    across entrypoints and is controlled by VAD_USER_SPEECH_TIMEOUT_SECS.
    """
    logger.info(
        f"[VAD] user_speech_timeout={VAD_USER_SPEECH_TIMEOUT_SECS}s "
        f"deepgram_endpointing_ms={DEEPGRAM_ENDPOINTING_MS}"
    )
    return UserTurnStrategies(
        stop=[
            SpeechTimeoutUserTurnStopStrategy(
                user_speech_timeout=VAD_USER_SPEECH_TIMEOUT_SECS
            )
        ]
    )


# One lock per session_id, shared across all BotManager instances in this process.
# On a fast re-open a second bot can spawn for the same link while the first is still
# finalizing; serializing here prevents two bots from interleaving writes to the same
# session row (last-writer-wins assessment loss).
# threading.Lock (NOT asyncio.Lock): two bots that resume the same session_id run on
# DIFFERENT event loops in different threads, and an asyncio.Lock only excludes
# coroutines on its own loop — it gave false mutual-exclusion across bots. A
# threading.Lock serializes across threads/loops correctly. _GUARD makes lazy creation
# of the per-session lock itself thread-safe.
_FINALIZE_LOCKS: dict[str, "threading.Lock"] = {}
_FINALIZE_LOCKS_GUARD = threading.Lock()


def _finalize_lock_for(session_id: str) -> "threading.Lock":
    with _FINALIZE_LOCKS_GUARD:
        lock = _FINALIZE_LOCKS.get(session_id)
        if lock is None:
            lock = threading.Lock()
            _FINALIZE_LOCKS[session_id] = lock
        return lock


class BotManager:
    """Manages the dual-LLM interview pipeline (Judge + Responder)."""

    def __init__(self, transport, stt, llm, tts, context, user_aggregator, assistant_aggregator):
        self.transport = transport
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.context = context
        self.user_aggregator = user_aggregator
        self.assistant_aggregator = assistant_aggregator

        # The interview session is configured per-candidate at connect time via
        # configure_session(); processors are built session-less and updated then.
        from events.broadcaster import broadcaster
        self.session = None
        self.resumed = False  # set True in configure_session when a prior transcript exists
        self.broadcaster = broadcaster

        # Initialize goal tracking service (session attached later)
        self.goal_service = None
        self.goal_processor = None
        if os.getenv("GOAL_TRACKING_ENABLED", "true").lower() == "true":
            groq_api_key = os.getenv("GROQ_API_KEY_GOAL") or os.getenv("GROQ_API_KEY")
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

        # Optional video recording: taps the candidate's incoming camera frames and
        # writes a video-only MP4 next to the WAV; muxed together at finalize.
        self.video_recorder = None
        if RECORD_VIDEO:
            from processors.video_recorder import VideoRecorderProcessor
            self.video_recorder = VideoRecorderProcessor(self._video_tmp_path)

        # Optional video analysis: samples the same camera frames and asks a vision
        # model for advisory presence/integrity/delivery observations (SSE + sidecar).
        self.vision_processor = None
        self._proctor_violation_count = 0
        if ANALYZE_VIDEO:
            from processors.vision_analysis_processor import VisionAnalysisProcessor
            self.vision_processor = VisionAnalysisProcessor(self.broadcaster)

            async def _handle_proctor_violation(flags: list) -> None:
                msg = None

                if "candidate_absent" in flags:
                    self._proctor_violation_count += 1
                    count = self._proctor_violation_count
                    if count == 1:
                        msg = (
                            "PROCTORING ALERT: The candidate is no longer visible on camera. "
                            "Say: 'I notice I can no longer see you on camera. Could you please "
                            "make sure your camera is on and you're visible? Take your time — "
                            "just let me know when you're ready to continue.'"
                        )
                    else:
                        msg = (
                            "PROCTORING ALERT: Candidate still not visible on camera. "
                            "Say: 'I'm still having trouble seeing you on camera. Please ensure "
                            "your camera is working and you're in frame before we continue.'"
                        )

                elif "multiple_people" in flags:
                    self._proctor_violation_count += 1
                    count = self._proctor_violation_count
                    if count == 1:
                        msg = (
                            "PROCTORING ALERT: The system has detected more than one person visible "
                            "on camera. You MUST pause and address this immediately. Say to the "
                            "candidate: 'I can see there is someone else on camera with you. For the "
                            "fairness and integrity of this interview, I need you to be in the room "
                            "alone. Could you please ask them to step out? Let me know when you're "
                            "ready and we'll continue.'"
                        )
                    elif count == 2:
                        msg = (
                            "PROCTORING ALERT: Multiple people on camera detected AGAIN (2nd time). "
                            "Issue a firm final warning: 'I'm seeing another person on camera again — "
                            "this is your final warning. You must be completely alone for this "
                            "interview. If I detect this one more time, I will need to end the session.'"
                        )
                    else:
                        msg = (
                            "PROCTORING VIOLATION: Multiple people on camera detected 3 times. "
                            "End the interview immediately. Say: 'I've now detected multiple people "
                            "on camera three times. I'm required to end this session to ensure "
                            "fairness for all candidates. The recruitment team will follow up with "
                            "you directly about next steps.' Then close the interview gracefully."
                        )
                        if hasattr(self, "session") and self.session:
                            self.session.end()

                elif "avatar_detected" in flags:
                    msg = (
                        "PROCTORING ALERT: The system suspects a virtual avatar or deepfake may be "
                        "in use instead of a live camera. Say: 'For the integrity of this interview, "
                        "I need to confirm you are on a live camera rather than a virtual image. "
                        "Could you briefly turn your head or wave so I can verify you are live? "
                        "Thank you.'"
                    )

                if msg is None:
                    return

                self.context.add_message({
                    "role": "user",
                    "content": f"[SYSTEM INSTRUCTION — not from candidate]: {msg}",
                })
                if hasattr(self, "worker") and self.worker:
                    await self.worker.queue_frames([LLMRunFrame()])

            self.vision_processor.on_violation = _handle_proctor_violation

        # Silence nudge: if the candidate goes quiet, the bot checks in and then wraps
        # up instead of sitting in dead air. Sits upstream of the TTS so it can speak.
        from processors.silence_nudge_processor import SilenceNudgeProcessor
        self.silence_processor = SilenceNudgeProcessor(self.broadcaster)

        logger.info("[BotManager] Initializing DUAL LLM pipeline (Judge + Responder)")
        self.pipeline = self._create_dual_pipeline()

        # Create worker.
        # idle_timeout_secs: a real candidate often pauses to think between answers;
        # the default idle window tore interviews down after ~1 min of silence (and
        # took voice + chat with it). Give a generous 10-minute idle window so normal
        # think-pauses don't end the call, while still freeing the slot if the
        # candidate truly vanishes (a participant disconnect ends it immediately).
        self.worker = PipelineWorker(
            self.pipeline,
            idle_timeout_secs=600,
            params=PipelineParams(
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
        )

    def _create_dual_pipeline(self):
        """Create dual LLM pipeline with judge and context-aware responder"""

        # Create judge processor
        api_key = os.getenv("GROQ_API_KEY_JUDGE") or os.getenv("GROQ_API_KEY")
        self.judge_processor = JudgeProcessor(self.session, self.broadcaster, api_key)

        # Create context enrichment processor
        self.context_processor = DualLLMContextProcessor(self.session, self.context)

        pipeline_processors = [self.transport.input()]
        if self.video_recorder:
            pipeline_processors.append(self.video_recorder)
        if self.vision_processor:
            pipeline_processors.append(self.vision_processor)
        # Debug: log audio frame counts and VAD events (remove once STT is confirmed working)
        pipeline_processors.append(_AudioDebugProcessor())
        # Batch STT (e.g. Groq Whisper) needs a VAD processor upstream to detect
        # speech boundaries and fire VADUserStartedSpeakingFrame / VADUserStoppedSpeakingFrame.
        # stop_secs=1.0: wait 1 s of silence before ending the segment — the default
        # 0.2 s was chopping every utterance into sub-second fragments, wrecking accuracy.
        if isinstance(self.stt, BaseWhisperSTTService):
            from pipecat.audio.vad.vad_analyzer import VADParams
            pipeline_processors.append(VADProcessor(
                vad_analyzer=SileroVADAnalyzer(
                    params=VADParams(start_secs=0.2, stop_secs=2.0, confidence=0.7, min_volume=0.6)
                )
            ))
        pipeline_processors += [
            self.stt,
            self.transcript_processor,
            # Judge evaluates in parallel (non-blocking)
            self.judge_processor,
        ]
        if self.silence_processor:
            pipeline_processors.append(self.silence_processor)

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

        await self.broadcaster.broadcast("pipeline_mode", {
            "mode": "dual",
            "description": "Dual LLM (Judge + Responder)"
        })

        logger.info("[BotManager] Worker started - Mode: dual (awaiting interview config)")

    def _session_processors(self):
        """All pipeline processors that need the per-interview session."""
        procs = [self.transcript_processor, self.metrics_processor]
        if self.vision_processor:
            procs.append(self.vision_processor)
        if self.silence_processor:
            procs.append(self.silence_processor)
        if self.goal_processor:
            procs.append(self.goal_processor)
        for attr in ("judge_processor", "context_processor"):
            p = getattr(self, attr, None)
            if p is not None:
                procs.append(p)
        return procs

    @staticmethod
    def _resume_context_summary(session) -> str:
        """Build the resume instruction for the LLM from the restored session state.

        The live pipeline is LLM-driven, so 'position' is conveyed as: the topics
        already covered (don't repeat them) and the next question to ask. The prior
        transcript is already in context; this just steers continuation."""
        from interview_session import GoalStatus
        questions = session.config.questions
        covered = [
            q.text for q in questions
            if session.question_states.get(q.id)
            and session.question_states[q.id].status in (GoalStatus.COVERED, GoalStatus.WEAK, GoalStatus.SKIPPED)
        ]
        parts = [
            "The candidate has rejoined an interview that was interrupted. "
            "Their prior conversation is already in the history above — do NOT restart, "
            "re-introduce yourself, or repeat questions already answered."
        ]
        # Deterministic-flow pipeline: a restored position is meaningful, so name the
        # covered topics and the exact next question. LLM-driven pipeline: no index is
        # tracked (it stays 0), so steer continuation from the transcript instead of
        # falsely naming the first question as "next".
        has_recorded_progress = bool(covered) or session.current_question_index > 0
        if has_recorded_progress:
            if covered:
                parts.append("Topics already covered: " + "; ".join(covered[:8]) + ".")
            next_q = session.current_question
            if next_q is not None:
                parts.append(f"Continue by asking the next question: {next_q.text}")
            else:
                parts.append("All planned questions are covered — briefly wrap up and close the interview.")
        else:
            parts.append(
                "Pick up the conversation naturally from where it left off, based on the "
                "history above, and move on to a question that has not been asked yet."
            )
        return " ".join(parts)

    async def configure_session(self, session) -> None:
        """Attach a per-interview session to the running pipeline (single concurrency).

        Sets the session on every processor, seeds the LLM context with the
        role-specific system prompt, and creates the DB session row + goals.
        """
        self.session = session
        for p in self._session_processors():
            if hasattr(p, "set_session"):
                p.set_session(session)

        # Per-session system prompt (LLM service is built config-free). This is NOT
        # optional — without the persona the responder has no instructions and the
        # whole interview degrades to gibberish, so fail loudly instead of swallowing.
        try:
            self.context.add_message(
                {"role": "system", "content": session.config.system_prompt}
            )
        except Exception as e:
            logger.error(f"[BotManager] Failed to seed system prompt into context: {e}")
            raise RuntimeError(f"interview cannot start without its system prompt: {e}") from e

        # Resume support: if this link was opened before, replay the prior conversation
        # into the LLM context so the bot continues with full memory instead of
        # restarting. self.resumed tells the greeting to say "welcome back" and let the
        # LLM pick up where it left off rather than re-running the intro.
        #
        # Resume detection is AUTHORITATIVE on the prior session row, not on transcript
        # row count: a session row only exists once a candidate has joined before, so any
        # non-completed prior status ('active' from a hard drop, or 'interrupted' from a
        # graceful finalize) means a re-open. Relying on transcript rows alone misfired —
        # the deterministic greeting/early questions are pushed straight to TTS and never
        # hit the LLM-aggregation persist path, so an early reload found zero rows and
        # restarted from the intro. (See runner._greet_once, which now also persists the
        # opening line so the replayed history is complete.)
        self.resumed = False
        try:
            from database import db_manager
            prior_status = await db_manager.get_session_status(session.session_id)
            prior = await db_manager.get_transcript(session.session_id)
            # A session row is created at VALIDATE time (status 'active') BEFORE the
            # candidate first joins, so 'active' alone is NOT a resume — that made fresh
            # interviews greet "Welcome back". Only resume when there's real prior
            # conversation persisted (the opening line is persisted now), or the prior
            # run was finalized as 'interrupted'.
            self.resumed = (prior_status == "interrupted") or bool(prior)

            if prior:
                for entry in prior:
                    role = "assistant" if entry.get("speaker") == "agent" else "user"
                    text = (entry.get("text") or "").strip()
                    if text:
                        self.context.add_message({"role": role, "content": text})

            if self.resumed:
                # Restore the exact question-flow position (deterministic pipeline) and
                # tell the LLM-driven pipeline which topics are already covered so it
                # continues with the next one instead of repeating.
                try:
                    progress = await db_manager.get_session_progress(session.session_id)
                    if progress:
                        session.restore_progress(
                            progress.get("current_question_index", 0),
                            progress.get("question_states", {}),
                        )
                except Exception as e:
                    logger.warning(f"[BotManager] Could not restore question progress: {e}")

                self.context.add_message({
                    "role": "system",
                    "content": self._resume_context_summary(session),
                })
                logger.info(
                    f"[BotManager] Resuming {session.session_id} (prior status='{prior_status}'): "
                    f"replayed {len(prior)} turns, next question index "
                    f"{session.current_question_index}"
                )
        except Exception as e:
            logger.warning(f"[BotManager] Could not restore prior session state: {e}")

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
        """Inject typed text (from /chat) as if the candidate had spoken it.

        Must enter the pipeline at the SOURCE via the worker's queue (not
        transport.input().push_frame, which does not propagate into the running
        pipeline's processor tasks — frames pushed that way are dropped, so the
        transcript processor never broadcasts the line, the silence-nudge timer
        never resets, and the user aggregator never commits a turn for the LLM).

        We queue a COMPLETE user turn — UserStartedSpeaking → Transcription →
        UserStoppedSpeaking — so the LLM user aggregator commits the turn on the
        stop boundary and the LLM actually replies (a bare TranscriptionFrame
        only buffers without triggering a response).
        """
        logger.info(f"[BotManager] Injecting manual text: {text}")

        from pipecat.frames.frames import (
            TranscriptionFrame,
            UserStartedSpeakingFrame,
            UserStoppedSpeakingFrame,
        )
        import time

        if not getattr(self, "worker", None):
            logger.warning("[BotManager] inject_text called before worker exists; dropping")
            return

        frame = TranscriptionFrame(
            text=text,
            user_id="manual-input",
            timestamp=str(time.time()),
        )
        await self.worker.queue_frames([
            UserStartedSpeakingFrame(),
            frame,
            UserStoppedSpeakingFrame(),
        ])

    def get_pipeline_info(self):
        """Get current pipeline configuration"""
        return {
            "mode": "dual",
            "has_judge": True,
            "judge_model": "llama-3.1-8b-instant",
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

    async def finalize_session(self, graceful: bool = True, terminal: bool = False):
        """Finalize this interview, serialized per session_id (see _FINALIZE_LOCKS).

        ``graceful`` is True when the interview reached its natural end (all questions
        covered); it drives the goal/score wrap-up analysis.

        ``terminal`` marks the LINK as spent regardless of graceful: when either party
        leaves the call the interview is OVER — the session is stamped 'completed' so
        re-opening the link cannot resume it. (Without terminal, a non-graceful end was
        stamped 'interrupted' and stayed resumable.) The recording, transcript, and
        analysis are still persisted for HR review either way.

        Called once when the bot's worker ends (see runner._make_and_run_bot).
        Note: the DB pool is a process-global shared by every concurrent bot and the
        HTTP API, so we must NOT close it here — that is owned by process shutdown,
        not by a single interview ending.
        """
        sid = self.session.session_id if self.session else None
        if sid is None:
            await self._finalize_unlocked(graceful, terminal)
            return
        # Acquire the cross-thread lock off the event loop so we don't block this
        # bot's loop while another bot's thread holds it.
        lock = _finalize_lock_for(sid)
        await asyncio.to_thread(lock.acquire)
        try:
            await self._finalize_unlocked(graceful, terminal)
        finally:
            lock.release()

    async def _finalize_unlocked(self, graceful: bool = True, terminal: bool = False):
        if getattr(self, "_finalized", False):
            return  # this bot already finalized; don't double-write
        self._finalized = True
        # Stop the silence monitor so it can't speak into a finalizing pipeline.
        if getattr(self, "silence_processor", None):
            try:
                await self.silence_processor.stop()
            except Exception as e:
                logger.debug(f"[BotManager] silence stop skipped: {e}")
        if self.goal_processor:
            try:
                await self.goal_processor.finalize_session_goals(graceful=graceful)
                logger.info("[BotManager] Session goals finalized")
            except Exception as e:
                logger.error(f"[BotManager] Failed to finalize goals: {e}")

        # Authoritatively stamp the terminal status. This guarantees a status even
        # when goals were never initialized / analysis failed (otherwise the session
        # stays 'active' forever and the link could be reused and overwritten), and
        # is idempotent with the status finalize_session_goals already wrote.
        if self.session:
            try:
                from database import db_manager
                await db_manager.mark_session_status(
                    self.session.session_id,
                    "completed" if (graceful or terminal) else "interrupted"
                )
            except Exception as e:
                logger.error(f"[BotManager] Failed to stamp session status: {e}")

        # Post interview result back to the main FastAPI backend so HR can see scores.
        if self.session and (graceful or terminal):
            try:
                import httpx
                backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
                admin_token = os.getenv("ADMIN_API_TOKEN", "")
                # session_id format: "{candidate_id}-{jti_prefix}"
                cand_id_str = self.session.session_id.split("-")[0]
                if cand_id_str.isdigit():
                    phase1 = getattr(self.session, "phase1_score", None)
                    phase2 = getattr(self.session, "phase2_score", None)
                    overall = round((phase1 or 0) + (phase2 or 0), 1) if (phase1 is not None) else None
                    passed  = (phase1 is not None and phase1 >= 60 and phase2 is not None)
                    payload = {
                        "phase1_score": phase1,
                        "phase2_score": phase2,
                        "overall_score": overall,
                        "passed": passed,
                    }
                    async with httpx.AsyncClient(timeout=10) as client:
                        r = await client.post(
                            f"{backend_url}/candidates/{cand_id_str}/interview-result",
                            json=payload,
                            headers={"Authorization": f"Bearer {admin_token}"},
                        )
                    if r.status_code == 200:
                        logger.info(f"[BotManager] Interview result posted for candidate {cand_id_str}: passed={passed}")
                    else:
                        logger.warning(f"[BotManager] Interview result callback HTTP {r.status_code}: {r.text[:200]}")
            except Exception as e:
                logger.error(f"[BotManager] Failed to post interview result to backend: {e}")

        # Persist the per-service token breakdown (STT/LLM-in/LLM-out/TTS).
        if self.metrics_processor:
            try:
                await self.metrics_processor.persist_summary()
            except Exception as e:
                logger.error(f"[BotManager] Failed to persist token summary: {e}")

        # Flush + persist the interview audio recording.
        await self._save_recording()
        # Mux the captured candidate video (if any) with the merged audio.
        await self._save_video()
        # Persist the advisory video-analysis observations.
        await self._save_vision()

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

    def _video_tmp_path(self) -> str | None:
        """Path for the intermediate video-only MP4 (the recorder writes here).

        Returns None until a session is attached — the recorder retries on the
        next frame, by which point the candidate has connected.
        """
        if not self.session:
            return None
        recordings_dir = os.getenv("RECORDINGS_DIR", "/mnt/muaaz/AI_recruiter/data/recordings")
        return os.path.join(recordings_dir, f"{self.session.session_id}.video.mp4")

    async def _save_video(self) -> None:
        """Mux the captured candidate video with the merged audio into {session}.mp4.

        Best-effort: if no video was captured (candidate kept camera off, PyAV
        missing, etc.) this is a no-op and the audio WAV stands on its own.
        """
        if not self.session or not self.video_recorder:
            return
        # Ensure the encoder is flushed/closed even if no EndFrame reached it.
        try:
            self.video_recorder.close()
        except Exception as e:
            logger.warning(f"[BotManager] video recorder close failed: {e}")

        video_only = self.video_recorder.video_path
        if not video_only or not os.path.exists(video_only):
            logger.info("[BotManager] No candidate video captured; skipping video save")
            return

        recordings_dir = os.getenv("RECORDINGS_DIR", "/mnt/muaaz/AI_recruiter/data/recordings")
        wav_path = os.path.join(recordings_dir, f"{self.session.session_id}.wav")
        final_path = os.path.join(recordings_dir, f"{self.session.session_id}.mp4")

        # If audio exists, mux it in; otherwise just promote the video-only file.
        if os.path.exists(wav_path):
            cmd = [
                "ffmpeg", "-y",
                "-i", video_only,
                "-i", wav_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-movflags", "+faststart",
                final_path,
            ]
        else:
            cmd = ["ffmpeg", "-y", "-i", video_only, "-c", "copy",
                   "-movflags", "+faststart", final_path]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(
                    f"[BotManager] ffmpeg mux failed (rc={proc.returncode}): "
                    f"{stderr.decode(errors='ignore')[-500:]}"
                )
                return
            try:
                os.remove(video_only)  # keep only the final muxed MP4
            except OSError:
                pass
            size = os.path.getsize(final_path)
            logger.info(f"[BotManager] Saved interview video: {final_path} ({size} bytes)")
        except FileNotFoundError:
            logger.error("[BotManager] ffmpeg not found on PATH; left video-only MP4 in place")
        except Exception as e:
            logger.error(f"[BotManager] Failed to mux interview video: {e}")

    async def _save_vision(self) -> None:
        """Stop the analyzer and write the advisory observations to a JSON sidecar.

        Best-effort and advisory-only: these observations are for human review and
        are deliberately NOT folded into the candidate's numeric score.
        """
        if not self.session or not self.vision_processor:
            return
        try:
            await self.vision_processor.stop()
        except Exception as e:
            logger.warning(f"[BotManager] vision stop failed: {e}")

        observations = self.vision_processor.observations
        detections = self.vision_processor.detections
        if not observations and not detections:
            logger.info("[BotManager] No video analysis captured; skipping vision save")
            return

        recordings_dir = os.getenv("RECORDINGS_DIR", "/mnt/muaaz/AI_recruiter/data/recordings")
        path = os.path.join(recordings_dir, f"{self.session.session_id}.vision.json")
        try:
            os.makedirs(recordings_dir, exist_ok=True)
            payload = {
                "session_id": self.session.session_id,
                "semantic_backend": self.vision_processor._backend,
                "advisory_only": True,
                "aggregate": self.vision_processor.aggregate(),
                "observations": observations,   # semantic VLM stream
                "detections": detections,        # local proctoring stream
            }
            import json as _json
            with open(path, "w") as f:
                _json.dump(payload, f, indent=2)
            logger.info(
                f"[BotManager] Saved video analysis: {path} "
                f"({len(observations)} semantic, {len(detections)} proctoring)"
            )
            # Broadcast the aggregate so the dashboard can show a summary at end.
            await self.broadcaster.broadcast("vision_summary", {
                "session_id": self.session.session_id,
                **payload["aggregate"],
            })
        except Exception as e:
            logger.error(f"[BotManager] Failed to save video analysis: {e}")