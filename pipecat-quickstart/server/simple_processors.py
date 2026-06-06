"""
Simple, working processors for the interview bot pipeline
"""

import json
import re
from loguru import logger
from pipecat.frames.frames import (
    Frame,
    TextFrame,
    TranscriptionFrame,
    LLMFullResponseStartFrame,
    LLMFullResponseEndFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.processors.frame_processor import FrameProcessor


class SimpleTranscriptAccumulator(FrameProcessor):
    """Records user transcripts from STT"""

    def __init__(self, session, broadcaster):
        super().__init__()
        self._session = session
        self._broadcaster = broadcaster

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        # Capture user speech
        if isinstance(frame, TranscriptionFrame):
            text = frame.text.strip()
            if text:
                logger.info(f"[TranscriptAccumulator] User said: {text}")

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

        # Pass frame through
        await self.push_frame(frame, direction)


class SimpleQuestionFlow(FrameProcessor):
    """Manages interview question flow"""

    def __init__(self, session, context):
        super().__init__()
        self._session = session
        self._context = context
        self._initial_message_sent = False

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        # Send initial question on first user speech
        if isinstance(frame, TranscriptionFrame) and not self._initial_message_sent:
            self._initial_message_sent = True
            logger.info("[QuestionFlow] Sending initial question")

            # Add initial context
            if self._session.current_question:
                question_text = self._session.current_question.text
                self._context.add_message({
                    "role": "system",
                    "content": f"Ask this question: {question_text}"
                })

        # Pass frame through
        await self.push_frame(frame, direction)


class SimpleLLMResponseHandler(FrameProcessor):
    """
    Handles LLM responses - extracts text, broadcasts transcripts
    Works with streaming text frames
    """

    def __init__(self, session, broadcaster):
        super().__init__()
        self._session = session
        self._broadcaster = broadcaster
        self._current_response = []
        self._response_started = False

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        # Track when response starts
        if isinstance(frame, LLMFullResponseStartFrame):
            self._response_started = True
            self._current_response = []
            logger.debug("[ResponseHandler] LLM response started")

        # Collect text frames during response
        elif isinstance(frame, TextFrame) and self._response_started:
            self._current_response.append(frame.text)
            # Pass text frame to TTS immediately
            await self.push_frame(frame, direction)
            return

        # Process complete response
        elif isinstance(frame, LLMFullResponseEndFrame):
            self._response_started = False

            # Get complete text
            full_text = ''.join(self._current_response)
            if not full_text:
                # Try to get text from frame itself
                full_text = getattr(frame, 'text', '')

            if full_text:
                logger.info(f"[ResponseHandler] Agent said: {full_text[:100]}...")

                # Try to extract JSON if present
                response_text = full_text
                try:
                    json_match = re.search(r'(\{.*\})', full_text, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group(1))
                        response_text = data.get("response", full_text)
                        evaluation = data.get("evaluation", {})

                        if evaluation:
                            self._session.add_evaluation(evaluation)
                            await self._broadcaster.broadcast("evaluation", {
                                "session_id": self._session.session_id,
                                "data": evaluation
                            })
                except:
                    pass  # Use full text if JSON parsing fails

                # Add to session
                self._session.add_turn(
                    speaker="agent",
                    text=response_text,
                    question_id=self._session.current_question.id if self._session.current_question else None
                )

                # Broadcast agent transcript
                await self._broadcaster.broadcast("transcript", {
                    "speaker": "agent",
                    "text": response_text
                })

            self._current_response = []

        # Pass frame through
        await self.push_frame(frame, direction)


class SimpleMetricsTracker(FrameProcessor):
    """Tracks token usage metrics"""

    def __init__(self, session, broadcaster):
        super().__init__()
        self._session = session
        self._broadcaster = broadcaster
        self._total_tokens = 0

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        # Check for metrics in LLM response end frames
        if isinstance(frame, LLMFullResponseEndFrame):
            # Try to get usage data
            usage = getattr(frame, 'usage', None)

            if usage:
                # Extract token counts
                prompt_tokens = 0
                completion_tokens = 0
                total_tokens = 0

                # Handle different usage object types
                if hasattr(usage, 'prompt_tokens'):
                    prompt_tokens = usage.prompt_tokens
                    completion_tokens = getattr(usage, 'completion_tokens', 0)
                    total_tokens = getattr(usage, 'total_tokens', prompt_tokens + completion_tokens)
                elif isinstance(usage, dict):
                    prompt_tokens = usage.get('prompt_tokens', 0)
                    completion_tokens = usage.get('completion_tokens', 0)
                    total_tokens = usage.get('total_tokens', prompt_tokens + completion_tokens)

                if total_tokens > 0:
                    self._total_tokens += total_tokens

                    logger.info(f"[MetricsTracker] Tokens - Prompt: {prompt_tokens}, "
                              f"Completion: {completion_tokens}, Total: {total_tokens}, "
                              f"Session: {self._total_tokens}")

                    # Broadcast metrics
                    await self._broadcaster.broadcast("metrics", {
                        "session_id": self._session.session_id,
                        "metrics": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens
                        },
                        "session_total": self._total_tokens
                    })
            else:
                # Log for debugging
                logger.debug("[MetricsTracker] No usage data in LLM response frame")

        # Also check for TTS events to track audio
        elif isinstance(frame, TTSStartedFrame):
            logger.debug("[MetricsTracker] TTS started")
            await self._broadcaster.broadcast("tts", {"status": "started"})

        elif isinstance(frame, TTSStoppedFrame):
            logger.debug("[MetricsTracker] TTS stopped")
            await self._broadcaster.broadcast("tts", {"status": "stopped"})

        # Pass frame through
        await self.push_frame(frame, direction)