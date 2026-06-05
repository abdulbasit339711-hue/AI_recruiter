from pipecat.frames.frames import Frame, LLMFullResponseEndFrame
from pipecat.processors.frame_processor import FrameProcessor

class MetricsTracker(FrameProcessor):
    """
    Captures LLM token usage from the pipeline and broadcasts it to the dashboard.
    """
    def __init__(self, session, broadcaster):
        super().__init__()
        self._session = session
        self._broadcaster = broadcaster

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)
        
        if isinstance(frame, LLMFullResponseEndFrame):
            # Pipecat usage metrics are stored in the frame's usage attribute
            usage = getattr(frame, "usage", None)
            if usage:
                metrics = {
                    "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(usage, "completion_tokens", 0),
                    "total_tokens": getattr(usage, "total_tokens", 0)
                }
                
                # 1. Update session state
                self._session.add_metrics(metrics)
                
                # 2. Broadcast to dashboard
                await self._broadcaster.broadcast("metrics", {
                    "session_id": self._session.session_id,
                    "metrics": metrics
                })
        
        await self.push_frame(frame, direction)
