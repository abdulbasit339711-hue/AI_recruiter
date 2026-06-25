"""
Silence / no-response nudge.

If the candidate goes quiet (no speech and no chat) for a while, the bot should
not just sit in dead air until the hard idle timeout. This processor watches for
activity and, after escalating silences, proactively speaks: first a gentle
"are you still there?", then a wrap-up line so the interview closes gracefully.

Activity signals visible to this processor (it sits between STT and the LLM):
  * StartFrame      -> pipeline started; begin the watcher after a grace period
  * TTSSpeakFrame   -> bot is about to speak (greeting / nudge injected upstream)
  * TranscriptionFrame -> candidate spoke or typed (resets, clears escalation)

LLMFullResponseEndFrame / TTSStoppedFrame flow DOWNSTREAM (away from this
processor), so we cannot rely on them to start the loop. Instead we start on
StartFrame with a configurable grace period so the greeting finishes before any
nudge can fire. We also keep handlers for those frames in case Pipecat ever
propagates them upstream — they are harmless no-ops if they never arrive.
"""

import asyncio
import os
import time

from loguru import logger
from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    StartFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

# Seconds of continuous silence before the next nudge fires.
SILENCE_NUDGE_SECS: float = float(os.getenv("SILENCE_NUDGE_SECS", "30"))

# Grace period after pipeline start before any nudge can fire.
# Must be longer than the greeting TTS duration (~3 s) plus any connection delay.
SILENCE_NUDGE_GRACE_SECS: float = float(os.getenv("SILENCE_NUDGE_GRACE_SECS", "15"))

_DEFAULT_NUDGES = [
    "Are you there?",
    "Take your time, I'm here whenever you're ready.",
    "It seems we may have lost connection. Thanks for your time — we'll be in touch soon.",
]


class SilenceNudgeProcessor(FrameProcessor):
    """Speak escalating nudges when the candidate is silent, then wrap up."""

    def __init__(self, broadcaster=None, nudges=None, interval_secs=None):
        super().__init__()
        self._broadcaster = broadcaster
        self._session = None
        self._nudges = nudges or _DEFAULT_NUDGES
        self._interval = interval_secs or SILENCE_NUDGE_SECS
        self._last_activity = None
        self._bot_speaking = False
        self._bot_has_spoken = False
        self._level = 0
        self._task = None
        self._stopped = False

    def set_session(self, session):
        self._session = session

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, StartFrame):
            # Start the watcher immediately; grace period inside _loop prevents
            # premature nudges while the greeting is playing.
            if self._task is None and not self._stopped:
                self._task = asyncio.create_task(self._loop())

        elif isinstance(frame, TTSSpeakFrame):
            # A TTSSpeakFrame injected at transport.input (greeting, or our own
            # nudge re-entering the pipeline) flows downstream through this processor.
            # Use it to mark that the bot has spoken and reset the activity clock.
            self._last_activity = time.monotonic()
            self._bot_has_spoken = True

        elif isinstance(frame, TranscriptionFrame):
            text = (getattr(frame, "text", "") or "").strip()
            if text:
                self._last_activity = time.monotonic()
                self._level = 0

        # Keep these in case Pipecat propagates them upstream in future versions.
        elif isinstance(frame, (LLMFullResponseStartFrame, TTSStartedFrame)):
            self._bot_speaking = True
            self._last_activity = time.monotonic()
        elif isinstance(frame, (LLMFullResponseEndFrame, TTSStoppedFrame)):
            self._bot_speaking = False
            self._bot_has_spoken = True
            self._last_activity = time.monotonic()

        elif isinstance(frame, (EndFrame, CancelFrame)):
            await self.stop()

        await self.push_frame(frame, direction)

    async def _loop(self):
        # Grace period — wait for the greeting to finish before watching for silence.
        await asyncio.sleep(SILENCE_NUDGE_GRACE_SECS)
        if self._last_activity is None:
            self._last_activity = time.monotonic()
        logger.info(f"[SilenceNudge] watching (interval={self._interval}s, grace={SILENCE_NUDGE_GRACE_SECS}s)")
        while not self._stopped:
            try:
                await asyncio.sleep(min(5.0, self._interval))
                if self._stopped or self._bot_speaking or self._last_activity is None:
                    continue
                if self._level >= len(self._nudges):
                    continue
                idle = time.monotonic() - self._last_activity
                if idle >= self._interval:
                    await self._nudge(self._nudges[self._level])
                    self._level += 1
                    self._last_activity = time.monotonic()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[SilenceNudge] tick failed: {e}")

    async def _nudge(self, text: str):
        sid = self._session.session_id if self._session else None
        logger.info(f"[SilenceNudge] level {self._level} -> speaking nudge")
        if self._broadcaster:
            try:
                await self._broadcaster.broadcast("transcript", {
                    "session_id": sid, "speaker": "agent", "text": text,
                })
            except Exception:
                pass
        if self._session is not None:
            try:
                from database import db_manager
                await db_manager.add_transcript_entry(sid, {
                    "speaker": "agent", "text": text,
                    "timestamp": str(time.time()), "tokens_estimated": len(text.split()),
                })
            except Exception as e:
                logger.debug(f"[SilenceNudge] persist skipped: {e}")
        await self.push_frame(TTSSpeakFrame(text), FrameDirection.DOWNSTREAM)

    async def stop(self):
        if self._stopped:
            return
        self._stopped = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
