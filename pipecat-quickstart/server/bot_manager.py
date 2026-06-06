import asyncio
import os
from loguru import logger
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker, PipelineParams
from pipecat.frames.frames import StartFrame, TranscriptionFrame
from pipecat.processors.aggregators.llm_response import LLMFullResponseAggregator
from bot import create_interview_session
from transcript_accumulator import TranscriptAccumulator
from question_flow_processor import QuestionFlowProcessor
from fixed_json_parser import FixedLLMResponseParser
from core.metrics import MetricsTracker
from events.broadcaster import broadcaster
from audio_debug import AudioDebugger, AudioPipelineValidator

logger.info(f"Broadcaster imported successfully: {broadcaster}")

class BotManager:
    def __init__(self, transport, stt, llm, tts, context, user_aggregator, assistant_aggregator):
        self.transport = transport
        self.session = create_interview_session()
        self.session.start()

        # Validate audio configuration
        AudioPipelineValidator.validate_transport(transport)
        AudioPipelineValidator.validate_services(stt, tts, llm)

        transcript_accumulator = TranscriptAccumulator(self.session, broadcaster)
        self.question_flow = QuestionFlowProcessor(self.session, context)
        response_parser = FixedLLMResponseParser(self.session, broadcaster)
        metrics_tracker = MetricsTracker(self.session, broadcaster)
        
        # Pipeline:
        # 1. Input & STT
        # 2. Accumulate Transcript (Candidate)
        # 3. Aggregate User Speech for LLM
        # 4. Handle Question Sequence
        # 5. LLM generates JSON tokens
        # 6. Parser buffers tokens, extracts natural text & evaluation
        # 7. Aggregate full response to get usage metrics
        # 8. TTS speaks the natural text
        # 9. Output to Room
        # 10. Aggregate Assistant Text for LLM context (Conversational memory)
        # 11. Track Token Metrics

        pipeline_components = [
            self.transport.input(),
            stt,
            transcript_accumulator,
            user_aggregator,
            self.question_flow,
            llm,
            response_parser,
            LLMFullResponseAggregator(),
            metrics_tracker,
            tts,
            self.transport.output(),
            assistant_aggregator,
        ]

        # Add audio debugging if DEBUG_MODE is enabled
        if os.getenv("DEBUG_MODE", "false").lower() == "true":
            logger.info("[BotManager] Audio debugging enabled")
            # Add audio debugger after STT and before TTS
            pipeline_components.insert(2, AudioDebugger("PostSTT"))
            pipeline_components.insert(-3, AudioDebugger("PreTTS"))

        self.pipeline = Pipeline(pipeline_components)
        
        self.worker = PipelineWorker(
            self.pipeline,
            params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        )

    async def start(self):
        # The worker will handle pushing the StartFrame.
        # QuestionFlowProcessor now handles triggering the opening on BotConnectedFrame.
        pass
        
    async def inject_text(self, text, user_id="candidate"):
        frame = TranscriptionFrame(text=text, user_id=user_id, timestamp="100")
        logger.info(f"Injecting frame: {frame}")
        await self.transport.input().push_frame(frame)
