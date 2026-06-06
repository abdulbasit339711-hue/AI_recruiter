# transcript_accumulator.py

from datetime import datetime
from loguru import logger
from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    LLMFullResponseEndFrame,
)
from pipecat.processors.frame_processor import FrameProcessor
from interview_session import InterviewSession
from events.broadcaster import broadcaster


class TranscriptAccumulator(FrameProcessor):
    """
    Silent observer that records every candidate and agent turn
    into session.transcript.

    Rules:
    - Never modifies or blocks frames — always passes them downstream
    - Never makes decisions — only records
    - Records STT output as candidate turns
    - Records completed LLM responses as agent turns
    """

    def __init__(self, session: InterviewSession, broadcaster):
        super().__init__()
        self._session = session
        self._broadcaster = broadcaster

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        # Log frame type for debugging
        logger.debug(f"[TranscriptAccumulator] Processing frame: {type(frame).__name__}")

        # Candidate spoke — STT produced a transcript
        if isinstance(frame, TranscriptionFrame):
            text = frame.text.strip()
            if text:
                question_id = (
                    self._session.current_question.id
                    if self._session.current_question else None
                )
                self._session.add_turn(
                    speaker="candidate",
                    text=text,
                    question_id=question_id,
                )
                logger.info(f"[TranscriptAccumulator] Candidate: {text}")

                # Broadcast to dashboard
                logger.info(f"[TranscriptAccumulator] Broadcasting transcript for candidate")
                await self._broadcaster.broadcast("transcript", {
                    "speaker": "candidate",
                    "text": text
                })

        # Always pass the frame through
        await self.push_frame(frame, direction)
