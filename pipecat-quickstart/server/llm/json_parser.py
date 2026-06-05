import json
from loguru import logger
from pipecat.frames.frames import Frame, TextFrame
from pipecat.processors.frame_processor import FrameProcessor

class LLMResponseParser(FrameProcessor):
    """
    Parses structured JSON from the LLM.
    Separates the conversational 'response' (for TTS) from the 'evaluation' (for Dashboard).
    """
    def __init__(self, session, broadcaster):
        super().__init__()
        self._session = session
        self._broadcaster = broadcaster

    async def process_frame(self, frame: Frame, direction):
        # Always pass all frames through to ensure pipeline integrity
        await self.push_frame(frame, direction)
        
        # Log for debugging
        if isinstance(frame, TextFrame):
            text = frame.text.strip()
            logger.info(f"LLMResponseParser processing TextFrame: {text}")

            try:
                # Attempt to parse JSON
                logger.info(f"LLM Raw Response: {text}")
                data = json.loads(text)
                response_text = data.get("response", "")
                evaluation = data.get("evaluation", {})

                # 1. Update session state
                if evaluation:
                    self._session.add_evaluation(evaluation)
                    # 2. Broadcast to dashboard
                    await self._broadcaster.broadcast("evaluation", {
                        "session_id": self._session.session_id,
                        "data": evaluation
                    })

                # 3. Handle response text
                if response_text:
                    logger.info(f"Agent: {response_text}")
                    # Broadcast to dashboard chat
                    await self._broadcaster.broadcast("transcript", {
                        "speaker": "agent",
                        "text": response_text
                    })
                    # Note: We already pushed the frame at the start, 
                    # but the original code pushed TextFrame(response_text) here.
                    # This might cause double frames. If TTS needs it, ensure we don't double-push.
                    # Given the current issue, let's keep it simple.

            except json.JSONDecodeError:
                logger.warning(f"LLM did not return valid JSON.")
        else:
            logger.debug(f"LLMResponseParser passed through: {type(frame)}")
