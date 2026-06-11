"""TTS that degrades gracefully instead of breaking the pipeline.

A TTS provider can fail mid-session — e.g. Cartesia returns HTTP 402 when the
account runs out of credits, which otherwise floods the pipeline with repeating
ErrorFrames ("Something went wrong") and leaves the bot silently broken. This
module wraps ANY pipecat TTS provider so it:

  * Swallows provider ErrorFrames so they never disrupt the pipeline.
  * On a quota/credit error, disables TTS for the rest of the session (no repeated
    402s / wasted latency) and records WHY in `degraded_reason`.
  * Lets the conversation continue as text — the agent's words are still broadcast
    to the dashboard before TTS — so an interview never hard-fails on TTS.

`degraded_reason` is surfaced in runner.py's /health so a dead TTS provider is
visible to operators instead of failing silently. To change providers, set
TTS_PROVIDER (see runner.py); that is the supported failover lever today.
"""

from typing import AsyncGenerator

from loguru import logger
from pipecat.frames.frames import ErrorFrame, Frame
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.tts import DeepgramTTSService

_QUOTA_MARKERS = ("quota_exceeded", "Insufficient credits", "status 402", "HTTP 402", "402")


def _make_resilient(base_cls):
    """Build a graceful-degradation subclass of a pipecat TTS provider class."""

    class _ResilientTTSService(base_cls):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._tts_disabled = False
            self.degraded_reason: str | None = None

        async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame | None, None]:
            # Once disabled (out of credits), skip the API entirely — no audio, but the
            # conversation/transcript keeps flowing.
            if self._tts_disabled:
                return
            async for frame in super().run_tts(text, context_id):
                if isinstance(frame, ErrorFrame):
                    err = str(getattr(frame, "error", frame))
                    if any(m in err for m in _QUOTA_MARKERS):
                        if not self._tts_disabled:
                            self._tts_disabled = True
                            self.degraded_reason = "quota/credits exhausted"
                            logger.warning(
                                f"[TTS] {base_cls.__name__} is out of credits — disabling "
                                "speech for this session; the interview continues as text "
                                "only. Top up the provider or set TTS_PROVIDER to switch."
                            )
                    else:
                        self.degraded_reason = err[:200]
                        logger.warning(f"[TTS] {base_cls.__name__} error, skipping audio this turn: {err}")
                    # Swallow the error frame — do not propagate it into the pipeline.
                    return
                yield frame

    _ResilientTTSService.__name__ = f"Resilient{base_cls.__name__}"
    return _ResilientTTSService


# Graceful-degradation variants of each supported provider.
ResilientCartesiaTTSService = _make_resilient(CartesiaTTSService)
ResilientDeepgramTTSService = _make_resilient(DeepgramTTSService)
