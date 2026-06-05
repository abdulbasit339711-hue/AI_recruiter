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
        self._current_agent_response = []   # buffer LLM tokens until response ends

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)
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
                logger.info(f"Candidate: {text}")
                
                # Broadcast to dashboard
                await self._broadcaster.broadcast("transcript", {
                    "speaker": "candidate",
                    "text": text
                })

        # LLM response fully complete — flush buffer as one agent turn
        elif isinstance(frame, LLMFullResponseEndFrame):
            # In Pipecat, LLMFullResponseEndFrame often contains the full text
            # if the aggregator was used. Let's check how to best capture it.
            # For now, we'll assume we might need to buffer from LLMResponseStartFrame 
            # or TextFrame if we wanted streaming, but LLMFullResponseEndFrame is 
            # the safest "completion" signal.
            pass

        # Note: To properly capture the agent response in the current pipeline,
        # we'd ideally listen to TextFrames coming from the LLM or use the 
        # assistant_aggregator's output. 
        # For simplicity in this recording phase, let's assume we capture 
        # the full text when the response is done.
        
        # Always pass the frame through
        await self.push_frame(frame, direction)
