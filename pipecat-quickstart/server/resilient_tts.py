"""TTS service that degrades gracefully instead of breaking the pipeline.

CartesiaTTSService.run_tts yields an ErrorFrame on failures (e.g. 402
quota_exceeded when the account runs out of credits). Those ErrorFrames flow
downstream as "Something went wrong" and repeat on every turn. This wrapper:

  * Swallows Cartesia ErrorFrames so they never disrupt the pipeline.
  * On a quota / credit error, disables TTS for the rest of the session and skips
    the API call on subsequent turns (no repeated 402s, no wasted latency).
  * Lets the conversation continue as text only — the agent's words are still
    broadcast to the dashboard by WorkingMetricsProcessor before TTS.
"""

from typing import AsyncGenerator

from loguru import logger
from pipecat.frames.frames import ErrorFrame, Frame
from pipecat.services.cartesia.tts import CartesiaTTSService

_QUOTA_MARKERS = ("quota_exceeded", "Insufficient credits", "status 402")


class ResilientCartesiaTTSService(CartesiaTTSService):
    """Cartesia WebSocket TTS (low latency) that fails gracefully (text-only fallback)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tts_disabled = False

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
                        logger.warning(
                            "[TTS] Cartesia is out of credits — disabling speech for this "
                            "session; the interview continues as text only. Top up or enable "
                            "overages at https://play.cartesia.ai/subscription"
                        )
                else:
                    logger.warning(f"[TTS] Cartesia error, skipping audio this turn: {err}")
                # Swallow the error frame — do not propagate it into the pipeline.
                return
            yield frame
