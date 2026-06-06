"""
Minimal working processors that don't break the audio pipeline
"""

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    TextFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameProcessor


class WorkingTranscriptProcessor(FrameProcessor):
    """
    Minimal processor that captures transcripts without blocking audio
    """

    def __init__(self, session, broadcaster):
        super().__init__()
        self._session = session
        self._broadcaster = broadcaster

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        # Only capture user transcription frames
        if isinstance(frame, TranscriptionFrame):
            text = frame.text.strip()
            if text:
                logger.info(f"[Transcript] User: {text[:100]}...")

                # Add to session
                self._session.add_turn(
                    speaker="candidate",
                    text=text,
                    question_id=self._session.current_question.id if self._session.current_question else None
                )

                # Broadcast to dashboard
                await self._broadcaster.broadcast("transcript", {
                    "speaker": "candidate",
                    "text": text
                })

        # Always pass frame through unchanged
        await self.push_frame(frame, direction)


class WorkingMetricsProcessor(FrameProcessor):
    """
    Minimal processor that captures agent responses and metrics
    """

    def __init__(self, session, broadcaster):
        super().__init__()
        self._session = session
        self._broadcaster = broadcaster
        self._current_response = []
        self._collecting = False
        self._total_tokens = 0

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        # Collect text frames that are going to TTS (agent responses)
        if isinstance(frame, TextFrame):
            # This is likely agent response text
            text = frame.text.strip()
            if text:
                logger.info(f"[Agent] Response: {text[:100]}...")

                # Add to session
                self._session.add_turn(
                    speaker="agent",
                    text=text,
                    question_id=self._session.current_question.id if self._session.current_question else None
                )

                # Broadcast agent transcript
                await self._broadcaster.broadcast("transcript", {
                    "speaker": "agent",
                    "text": text
                })

                # Simulate metrics (since we might not get usage data from frames)
                # In real scenario, this would come from LLM response frames
                estimated_tokens = len(text.split()) * 1.3  # Rough estimate
                self._total_tokens += int(estimated_tokens)

                await self._broadcaster.broadcast("metrics", {
                    "session_id": self._session.session_id,
                    "metrics": {
                        "prompt_tokens": int(estimated_tokens * 0.7),
                        "completion_tokens": int(estimated_tokens * 0.3),
                        "total_tokens": int(estimated_tokens)
                    }
                })

                logger.info(f"[Metrics] Estimated tokens: {int(estimated_tokens)}, Session total: {self._total_tokens}")

        # Pass frame through unchanged
        await self.push_frame(frame, direction)