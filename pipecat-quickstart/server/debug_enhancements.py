# Debug Enhancements for Pipecat Voice Agent
# This module provides enhanced debugging capabilities for the interview bot

import asyncio
from datetime import datetime
from loguru import logger
from pipecat.frames.frames import (
    Frame,
    TextFrame,
    TranscriptionFrame,
    LLMFullResponseEndFrame,
    StartFrame,
    EndFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameProcessor

class DebugFrameLogger(FrameProcessor):
    """
    Comprehensive frame logger that tracks all frame types passing through the pipeline.
    Helps identify where frames are getting lost or modified.
    """

    def __init__(self, name: str, log_level: str = "DEBUG"):
        super().__init__()
        self.name = name
        self.log_level = log_level
        self.frame_counts = {}
        self.last_logged = datetime.now()

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        frame_type = type(frame).__name__
        self.frame_counts[frame_type] = self.frame_counts.get(frame_type, 0) + 1

        # Log specific important frames
        if isinstance(frame, (TranscriptionFrame, TextFrame, LLMFullResponseEndFrame)):
            logger.log(
                self.log_level,
                f"[{self.name}] {frame_type}: {getattr(frame, 'text', getattr(frame, 'usage', 'N/A'))[:100]}"
            )
        elif isinstance(frame, (StartFrame, EndFrame)):
            logger.info(f"[{self.name}] Pipeline {frame_type} detected")
        elif isinstance(frame, (UserStartedSpeakingFrame, UserStoppedSpeakingFrame)):
            logger.debug(f"[{self.name}] User speech event: {frame_type}")
        elif isinstance(frame, (TTSStartedFrame, TTSStoppedFrame)):
            logger.debug(f"[{self.name}] TTS event: {frame_type}")

        # Periodic stats logging (every 10 seconds)
        now = datetime.now()
        if (now - self.last_logged).total_seconds() > 10:
            logger.info(f"[{self.name}] Frame counts: {self.frame_counts}")
            self.last_logged = now

        await self.push_frame(frame, direction)


class MetricsDebugger(FrameProcessor):
    """
    Enhanced metrics debugger that provides detailed token usage information.
    """

    def __init__(self, session, broadcaster):
        super().__init__()
        self._session = session
        self._broadcaster = broadcaster
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.response_count = 0

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMFullResponseEndFrame):
            self.response_count += 1
            usage = getattr(frame, "usage", None)

            if usage:
                prompt_tokens = getattr(usage, "prompt_tokens", 0)
                completion_tokens = getattr(usage, "completion_tokens", 0)
                total_tokens = getattr(usage, "total_tokens", 0)

                self.total_prompt_tokens += prompt_tokens
                self.total_completion_tokens += completion_tokens

                logger.info(
                    f"[METRICS] Response #{self.response_count} - "
                    f"Prompt: {prompt_tokens}, Completion: {completion_tokens}, "
                    f"Total: {total_tokens} | "
                    f"Session Total: {self.total_prompt_tokens + self.total_completion_tokens}"
                )

                # Broadcast detailed metrics
                await self._broadcaster.broadcast("metrics_debug", {
                    "response_number": self.response_count,
                    "current": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens
                    },
                    "session_total": {
                        "prompt_tokens": self.total_prompt_tokens,
                        "completion_tokens": self.total_completion_tokens,
                        "total_tokens": self.total_prompt_tokens + self.total_completion_tokens
                    },
                    "timestamp": datetime.now().isoformat()
                })
            else:
                logger.warning(f"[METRICS] Response #{self.response_count} - No usage data available!")

        await self.push_frame(frame, direction)


class TranscriptDebugger(FrameProcessor):
    """
    Enhanced transcript debugger that ensures all conversation turns are captured.
    """

    def __init__(self, session, broadcaster):
        super().__init__()
        self._session = session
        self._broadcaster = broadcaster
        self.turn_count = {"candidate": 0, "agent": 0}

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            text = frame.text.strip()
            if text:
                self.turn_count["candidate"] += 1
                logger.info(
                    f"[TRANSCRIPT] Candidate Turn #{self.turn_count['candidate']}: {text[:100]}..."
                )

                # Double-check broadcast
                await self._broadcaster.broadcast("transcript_debug", {
                    "speaker": "candidate",
                    "text": text,
                    "turn_number": self.turn_count["candidate"],
                    "timestamp": datetime.now().isoformat()
                })

        await self.push_frame(frame, direction)


class PipelineHealthMonitor:
    """
    Monitors overall pipeline health and provides diagnostic information.
    """

    def __init__(self, session, broadcaster):
        self.session = session
        self.broadcaster = broadcaster
        self.start_time = datetime.now()
        self.last_activity = datetime.now()
        self.health_check_task = None

    async def start_monitoring(self):
        """Start the health monitoring task."""
        self.health_check_task = asyncio.create_task(self._health_check_loop())

    async def stop_monitoring(self):
        """Stop the health monitoring task."""
        if self.health_check_task:
            self.health_check_task.cancel()

    async def _health_check_loop(self):
        """Periodic health check every 5 seconds."""
        while True:
            await asyncio.sleep(5)

            now = datetime.now()
            uptime = (now - self.start_time).total_seconds()
            idle_time = (now - self.last_activity).total_seconds()

            health_status = {
                "uptime_seconds": uptime,
                "idle_seconds": idle_time,
                "session_id": self.session.session_id,
                "transcript_length": len(self.session.transcript),
                "current_question": self.session.current_question.id if self.session.current_question else None,
                "timestamp": now.isoformat()
            }

            logger.debug(f"[HEALTH] Pipeline status: {health_status}")
            await self.broadcaster.broadcast("health", health_status)

    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.now()


# Utility function to inject debug processors into pipeline
def inject_debug_processors(pipeline_processors: list, session, broadcaster) -> list:
    """
    Inject debug processors at strategic points in the pipeline.

    Args:
        pipeline_processors: Original list of pipeline processors
        session: Interview session
        broadcaster: Event broadcaster

    Returns:
        Enhanced pipeline with debug processors
    """

    enhanced = []

    for i, processor in enumerate(pipeline_processors):
        # Add frame logger before each major component
        if i == 0:
            enhanced.append(DebugFrameLogger("INPUT", "INFO"))
        elif "stt" in str(type(processor)).lower():
            enhanced.append(DebugFrameLogger("PRE-STT", "DEBUG"))
        elif "llm" in str(type(processor)).lower():
            enhanced.append(DebugFrameLogger("PRE-LLM", "DEBUG"))
        elif "tts" in str(type(processor)).lower():
            enhanced.append(DebugFrameLogger("PRE-TTS", "DEBUG"))

        enhanced.append(processor)

        # Add specific debuggers after certain components
        if "transcript" in str(type(processor)).lower():
            enhanced.append(TranscriptDebugger(session, broadcaster))
        elif "metrics" in str(type(processor)).lower():
            enhanced.append(MetricsDebugger(session, broadcaster))

    enhanced.append(DebugFrameLogger("OUTPUT", "INFO"))

    return enhanced


# Example usage in bot_manager.py or bot.py:
"""
from debug_enhancements import inject_debug_processors, PipelineHealthMonitor

# In your bot initialization:
if os.getenv("DEBUG_MODE", "false").lower() == "true":
    pipeline_processors = inject_debug_processors(
        pipeline_processors,
        session,
        broadcaster
    )

    health_monitor = PipelineHealthMonitor(session, broadcaster)
    await health_monitor.start_monitoring()
"""