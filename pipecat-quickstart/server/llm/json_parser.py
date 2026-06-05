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
        await super().process_frame(frame, direction)
        
        if isinstance(frame, TextFrame):
            text = frame.text.strip()
            if not text:
                return

            try:
                # Attempt to parse JSON
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

                # 3. Push ONLY the spoken text forward to TTS
                if response_text:
                    # Broadcast to dashboard chat
                    await self._broadcaster.broadcast("transcript", {
                        "speaker": "agent",
                        "text": response_text
                    })
                    await self.push_frame(TextFrame(response_text))
                else:
                    # Fallback if response key is missing
                    await self.push_frame(frame)

            except json.JSONDecodeError:
                # LLM might have returned plain text despite instructions
                logger.warning(f"LLM did not return valid JSON. Text starts with: {text[:50]}")
                # Broadcast plain text as agent response to ensure chat visibility
                await self._broadcaster.broadcast("transcript", {
                    "speaker": "agent",
                    "text": text
                })
                await self.push_frame(frame)
        else:
            # Pass all other frames through
            await self.push_frame(frame, direction)
