"""
Silence / no-response nudge.

If the candidate goes quiet (no speech and no chat) for a while, the bot should
not just sit in dead air until the hard idle timeout. This processor watches for
activity and, after escalating silences, proactively speaks: first a gentle
"are you still there?", then a wrap-up line so the interview closes gracefully.

Activity signals (chosen so they're all visible UPSTREAM of the TTS, where this
processor must sit to push speech into it):
  * TranscriptionFrame        -> candidate spoke or typed  (resets, clears escalation)
  * LLMFullResponseStartFrame -> bot is responding         (mute nudges while talking)
  * LLMFullResponseEndFrame   -> bot finished responding   (start counting silence here)

It speaks by pushing a TTSSpeakFrame downstream (same mechanism as the greeting),
so it must sit upstream of the TTS service in the pipeline. Best-effort: any error
is logged and the interview continues.
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
    TranscriptionFrame,
    TTSSpeakFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

# Seconds of continuous silence before the next nudge fires.
SILENCE_NUDGE_SECS: float = float(os.getenv("SILENCE_NUDGE_SECS", "30"))

# Escalating lines: gentle check-in(s) first, wrap-up last. After the last one the
# processor goes quiet (the hard idle timeout / disconnect handler ends the call).
_DEFAULT_NUDGES = [
    "Still there?",
    "Take your time — I'm here.",
    "Looks like we may have lost the connection. Thanks for your time — we'll follow up soon.",
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
        self._level = 0          # how many nudges fired since the last candidate reply
        self._task = None
        self._stopped = False

    def set_session(self, session):
        self._session = session

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            text = (getattr(frame, "text", "") or "").strip()
            if text:
                # Candidate spoke/typed — reset silence and the escalation level.
                self._last_activity = time.monotonic()
                self._level = 0
        elif isinstance(frame, LLMFullResponseStartFrame):
            self._bot_speaking = True
            self._last_activity = time.monotonic()
        elif isinstance(frame, LLMFullResponseEndFrame):
            self._bot_speaking = False
            # Start counting silence from when the bot finishes its reply.
            self._last_activity = time.monotonic()
        elif isinstance(frame, (EndFrame, CancelFrame)):
            await self.stop()

        if self._task is None and not self._stopped:
            self._last_activity = time.monotonic()
            self._task = asyncio.create_task(self._loop())

        await self.push_frame(frame, direction)

    async def _loop(self):
        logger.info(f"[SilenceNudge] watching (every {self._interval}s of silence)")
        while not self._stopped:
            try:
                await asyncio.sleep(min(5.0, self._interval))
                if self._stopped or self._bot_speaking or self._last_activity is None:
                    continue
                if self._level >= len(self._nudges):
                    continue  # already wrapped up; stay quiet
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
        # Persist so the nudge shows in the transcript / replay.
        if self._session is not None:
            try:
                from database import db_manager
                await db_manager.add_transcript_entry(sid, {
                    "speaker": "agent", "text": text,
                    "timestamp": str(time.time()), "tokens_estimated": len(text.split()),
                })
            except Exception as e:
                logger.debug(f"[SilenceNudge] persist skipped: {e}")
        # Speak it. Pushed DOWNSTREAM toward the TTS (this processor sits upstream of it).
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
