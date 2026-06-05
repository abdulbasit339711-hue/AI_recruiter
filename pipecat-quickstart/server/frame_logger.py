from loguru import logger
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames.frames import Frame

class FrameLogger(FrameProcessor):
    def __init__(self, name):
        super().__init__()
        self.logger_name = name

    async def process_frame(self, frame: Frame, direction):
        logger.debug(f"FrameLogger ({self.logger_name}) received frame: {type(frame)}")
        await self.push_frame(frame, direction)
