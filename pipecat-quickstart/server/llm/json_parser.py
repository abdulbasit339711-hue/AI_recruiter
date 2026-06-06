import json
import re
from loguru import logger
from pipecat.frames.frames import Frame, TextFrame, LLMFullResponseEndFrame, LLMFullResponseStartFrame
from pipecat.processors.frame_processor import FrameProcessor

class LLMResponseParser(FrameProcessor):
    """
    Robust JSON parser for LLM streaming responses.
    Uses regex to extract JSON objects and handles malformed output gracefully.
    """
    def __init__(self, session, broadcaster):
        super().__init__()
        self._session = session
        self._broadcaster = broadcaster
        self._buffer = []

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        logger.debug(f"[LLMResponseParser] Processing frame: {type(frame).__name__}")

        if isinstance(frame, LLMFullResponseStartFrame):
            # Reset buffer when starting new response
            self._buffer = []
            logger.debug("[LLMResponseParser] Starting new response aggregation")
            await self.push_frame(frame, direction)
            return

        elif isinstance(frame, TextFrame):
            self._buffer.append(frame.text)
            logger.debug(f"[LLMResponseParser] Buffering text: {frame.text[:50]}...")
            # Don't return here - let the frame pass through for other processors
            await self.push_frame(frame, direction)
            return

        elif isinstance(frame, LLMFullResponseEndFrame):
            logger.info("[LLMResponseParser] Processing LLMFullResponseEndFrame")

            # Get the full response text from the frame if available
            full_text = getattr(frame, 'text', None)
            if not full_text and self._buffer:
                full_text = "".join(self._buffer).strip()

            self._buffer = []

            if not full_text:
                await self.push_frame(frame, direction)
                return

            try:
                # 1. Try to find JSON block using regex if direct load fails
                json_match = re.search(r'(\{.*\})', full_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    data = json.loads(json_str)
                else:
                    raise json.JSONDecodeError("No JSON found", full_text, 0)
                
                if not isinstance(data, dict):
                    raise ValueError("Parsed JSON is not an object")

                response_text = data.get("response", "")
                evaluation = data.get("evaluation", {})

                # Broadcast Evaluation
                if evaluation:
                    self._session.add_evaluation(evaluation)
                    await self._broadcaster.broadcast("evaluation", {
                        "session_id": self._session.session_id,
                        "data": evaluation
                    })

                # Broadcast and Push Transcript
                if response_text:
                    logger.info(f"[LLMResponseParser] Agent: {response_text}")
                    self._session.add_turn(
                        speaker="agent",
                        text=response_text,
                        question_id=self._session.current_question.id if self._session.current_question else None
                    )
                    logger.info(f"[LLMResponseParser] Broadcasting agent transcript")
                    await self._broadcaster.broadcast("transcript", {
                        "speaker": "agent",
                        "text": response_text
                    })
                    # Push natural text to TTS - create a new TextFrame
                    clean_text_frame = TextFrame(text=response_text)
                    logger.debug(f"[LLMResponseParser] Pushing text to TTS: {response_text[:50]}...")
                    await self.push_frame(clean_text_frame, direction)

            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse JSON, falling back to raw text. Error: {e}")
                # Fallback: Treat as plain text
                await self._broadcaster.broadcast("transcript", {"speaker": "agent", "text": full_text})
                await self.push_frame(TextFrame(full_text), direction)
            
            await self.push_frame(frame, direction)
        else:
            await self.push_frame(frame, direction)
