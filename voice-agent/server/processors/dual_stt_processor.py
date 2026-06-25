"""
DualBatchSTTProcessor — races Deepgram prerecorded API and Groq Whisper in parallel
on every speech segment (gated by upstream VADProcessor).  First non-empty transcript
wins; the other in-flight request is cancelled.

Pipeline slot: place AFTER VADProcessor, BEFORE the transcript processor.
Replaces both DeepgramSTTService and GroqSTTService in the pipeline.
"""

import asyncio
import io
import os
import wave

import httpx
from loguru import logger
from pipecat.frames.frames import (
    AudioRawFrame,
    CancelFrame,
    EndFrame,
    Frame,
    StartFrame,
    TranscriptionFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.utils.time import time_now_iso8601


class DualBatchSTTProcessor(FrameProcessor):
    """Transcribes each VAD-gated speech segment with both Deepgram and Groq Whisper
    concurrently.  First non-empty result is pushed as a TranscriptionFrame; the other
    request is cancelled.  Falls back to whichever responds if the first returns empty."""

    def __init__(
        self,
        *,
        deepgram_api_key: str | None = None,
        groq_api_key: str | None = None,
        sample_rate: int = 16000,
        language: str = "en",
    ):
        super().__init__()
        self._dg_key = deepgram_api_key or os.environ.get("DEEPGRAM_API_KEY", "")
        self._groq_key = groq_api_key or os.environ.get("GROQ_API_KEY", "")
        self._sample_rate = sample_rate
        self._language = language
        self._speaking = False
        self._audio_buf = bytearray()
        self._tasks: set[asyncio.Task] = set()

    # ------------------------------------------------------------------
    # Frame routing
    # ------------------------------------------------------------------

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, VADUserStartedSpeakingFrame):
            self._speaking = True
            self._audio_buf = bytearray()

        elif isinstance(frame, AudioRawFrame):
            if self._speaking:
                self._audio_buf.extend(frame.audio)

        elif isinstance(frame, VADUserStoppedSpeakingFrame):
            self._speaking = False
            if self._audio_buf:
                audio = bytes(self._audio_buf)
                self._audio_buf = bytearray()
                t = asyncio.create_task(self._race(audio))
                self._tasks.add(t)
                t.add_done_callback(self._tasks.discard)

        elif isinstance(frame, (EndFrame, CancelFrame)):
            for t in list(self._tasks):
                t.cancel()

        await self.push_frame(frame, direction)

    # ------------------------------------------------------------------
    # Racing logic
    # ------------------------------------------------------------------

    async def _race(self, pcm: bytes):
        wav = self._pcm_to_wav(pcm)
        dg_task = asyncio.create_task(self._deepgram(wav))
        groq_task = asyncio.create_task(self._groq(wav))

        text = ""
        pending = {dg_task, groq_task}

        while pending and not text:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for t in done:
                try:
                    result = t.result()
                    if result:
                        text = result
                except Exception as exc:
                    logger.debug(f"[DualSTT] task raised: {exc}")

        for t in pending:
            t.cancel()

        if text:
            logger.info(f"[DualSTT] transcript: '{text}'")
            await self.push_frame(
                TranscriptionFrame(text, "", time_now_iso8601()),
                FrameDirection.DOWNSTREAM,
            )
        else:
            logger.warning("[DualSTT] both STT engines returned empty for this segment")

    # ------------------------------------------------------------------
    # Individual engine calls
    # ------------------------------------------------------------------

    async def _deepgram(self, wav: bytes) -> str:
        url = (
            f"https://api.deepgram.com/v1/listen"
            f"?model=nova-3&smart_format=true&language={self._language}"
        )
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.post(
                    url,
                    content=wav,
                    headers={
                        "Authorization": f"Token {self._dg_key}",
                        "Content-Type": "audio/wav",
                    },
                )
                r.raise_for_status()
                text = (
                    r.json()["results"]["channels"][0]["alternatives"][0]["transcript"]
                ).strip()
                logger.debug(f"[DualSTT] Deepgram: '{text}'")
                return text
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug(f"[DualSTT] Deepgram error: {exc}")
            return ""

    async def _groq(self, wav: bytes) -> str:
        try:
            from groq import AsyncGroq

            client = AsyncGroq(api_key=self._groq_key)
            resp = await client.audio.transcriptions.create(
                file=("audio.wav", wav, "audio/wav"),
                model="whisper-large-v3-turbo",
                response_format="json",
                language=self._language,
            )
            text = (resp.text or "").strip()
            logger.debug(f"[DualSTT] Groq Whisper: '{text}'")
            return text
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug(f"[DualSTT] Groq error: {exc}")
            return ""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _pcm_to_wav(self, pcm: bytes) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self._sample_rate)
            wf.writeframes(pcm)
        return buf.getvalue()
