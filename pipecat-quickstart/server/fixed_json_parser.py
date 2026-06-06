"""
Fixed JSON Parser that properly handles LLM responses without blocking audio
"""

import json
import re
from loguru import logger
from pipecat.frames.frames import Frame, TextFrame, LLMFullResponseEndFrame
from pipecat.processors.frame_processor import FrameProcessor


class FixedLLMResponseParser(FrameProcessor):
    """
    Fixed parser that correctly handles streaming LLM responses
    and works with LLMFullResponseAggregator
    """

    def __init__(self, session, broadcaster):
        super().__init__()
        self._session = session
        self._broadcaster = broadcaster

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        # Only process LLMFullResponseEndFrame from the aggregator
        if isinstance(frame, LLMFullResponseEndFrame):
            logger.info("[FixedParser] Processing aggregated LLM response")

            # Get the complete response text from the aggregator
            full_text = getattr(frame, 'text', '')

            if not full_text:
                logger.warning("[FixedParser] Empty response from LLM")
                await self.push_frame(frame, direction)
                return

            try:
                # Try to parse as JSON
                json_match = re.search(r'(\{.*\})', full_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    data = json.loads(json_str)
                else:
                    # If no JSON, treat entire response as text
                    data = {"response": full_text}

                response_text = data.get("response", full_text)
                evaluation = data.get("evaluation", {})

                # Broadcast evaluation if present
                if evaluation:
                    self._session.add_evaluation(evaluation)
                    await self._broadcaster.broadcast("evaluation", {
                        "session_id": self._session.session_id,
                        "data": evaluation
                    })
                    logger.info(f"[FixedParser] Evaluation: {evaluation}")

                # Add to transcript and broadcast
                if response_text:
                    logger.info(f"[FixedParser] Agent response: {response_text[:100]}...")

                    self._session.add_turn(
                        speaker="agent",
                        text=response_text,
                        question_id=self._session.current_question.id if self._session.current_question else None
                    )

                    await self._broadcaster.broadcast("transcript", {
                        "speaker": "agent",
                        "text": response_text
                    })

                    # CRITICAL: Send clean text to TTS
                    # Create a new TextFrame for TTS
                    tts_frame = TextFrame(text=response_text)
                    logger.info("[FixedParser] Sending text to TTS")
                    await self.push_frame(tts_frame, direction)

            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"[FixedParser] JSON parse failed, using raw text: {e}")

                # Fallback: Use entire response as text
                await self._broadcaster.broadcast("transcript", {
                    "speaker": "agent",
                    "text": full_text
                })

                # Send to TTS
                tts_frame = TextFrame(text=full_text)
                await self.push_frame(tts_frame, direction)

            # Pass the original frame through for metrics tracking
            await self.push_frame(frame, direction)

        else:
            # Pass all other frames through unchanged
            await self.push_frame(frame, direction)