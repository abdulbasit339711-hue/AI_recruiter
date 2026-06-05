
import asyncio
import os
from loguru import logger
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker, PipelineParams
from pipecat.frames.frames import StartFrame, TranscriptionFrame
from bot import create_interview_session
from transcript_accumulator import TranscriptAccumulator
from question_flow_processor import QuestionFlowProcessor
from llm.json_parser import LLMResponseParser
from core.metrics import MetricsTracker
from events.broadcaster import broadcaster

class BotManager:
    def __init__(self, transport, stt, llm, tts, context, user_aggregator, assistant_aggregator):
        self.transport = transport
        self.session = create_interview_session()
        self.session.start()
        
        transcript_accumulator = TranscriptAccumulator(self.session, broadcaster)
        question_flow = QuestionFlowProcessor(self.session, context)
        response_parser = LLMResponseParser(self.session, broadcaster)
        metrics_tracker = MetricsTracker(self.session, broadcaster)
        
        self.pipeline = Pipeline([
            self.transport.input(),
            # stt,
            transcript_accumulator,
            user_aggregator,
            question_flow,
            llm,
            assistant_aggregator,
            response_parser,
            tts,
            self.transport.output(),
            metrics_tracker,
        ])
        
        self.worker = PipelineWorker(
            self.pipeline,
            params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        )

    async def start(self):
        # Push StartFrame to the pipeline to initialize all processors
        await self.pipeline.queue_frame(StartFrame())
        
    async def inject_text(self, text, user_id="candidate"):
        frame = TranscriptionFrame(text=text, user_id=user_id, timestamp="100")
        logger.info(f"Injecting frame: {frame}")
        await self.transport.input().push_frame(frame)
