#!/usr/bin/env python3
"""
Minimal test to verify the pipeline is working
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
from loguru import logger

from pipecat.frames.frames import Frame, TextFrame, TranscriptionFrame, LLMFullResponseEndFrame
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker

# Remove default logger
try:
    logger.remove(0)
except Exception:
    pass
logger.add(sys.stderr, level="DEBUG")

load_dotenv(override=True)


class DebugProcessor(FrameProcessor):
    """Simple processor that logs all frames"""

    def __init__(self, name):
        super().__init__()
        self.name = name
        self.frame_count = 0

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        self.frame_count += 1
        frame_type = type(frame).__name__

        # Log important frames
        if isinstance(frame, (TextFrame, TranscriptionFrame, LLMFullResponseEndFrame)):
            logger.info(f"[{self.name}] Frame #{self.frame_count}: {frame_type}")

            if isinstance(frame, TextFrame):
                logger.info(f"  Text: {frame.text[:100]}...")
            elif isinstance(frame, TranscriptionFrame):
                logger.info(f"  Transcript: {frame.text}")
            elif isinstance(frame, LLMFullResponseEndFrame):
                usage = getattr(frame, 'usage', None)
                text = getattr(frame, 'text', None)
                logger.info(f"  Usage: {usage}")
                logger.info(f"  Text: {text[:100] if text else 'None'}...")

        # Pass frame through
        await self.push_frame(frame, direction)


async def test_basic_pipeline():
    """Test basic pipeline flow"""

    logger.info("=" * 60)
    logger.info("MINIMAL PIPELINE TEST")
    logger.info("=" * 60)

    from pipecat.transports.local.audio import LocalAudioTransport
    from pipecat.services.deepgram.stt import DeepgramSTTService
    from pipecat.services.groq.llm import GroqLLMService
    from pipecat.services.cartesia.tts import CartesiaHttpTTSService
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import (
        LLMContextAggregatorPair,
        LLMUserAggregatorParams,
    )
    from pipecat.processors.aggregators.llm_response import LLMFullResponseAggregator
    from pipecat.turns.user_turn_strategies import UserTurnStrategies
    from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import SpeechTimeoutUserTurnStopStrategy

    # Create transport
    transport = LocalAudioTransport()

    # Create services
    stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"])

    llm = GroqLLMService(
        api_key=os.environ["GROQ_API_KEY"],
        settings=GroqLLMService.Settings(
            model="llama-3.3-70b-versatile",
            system_instruction="You are a helpful test assistant. Keep responses very short."
        )
    )

    tts = CartesiaHttpTTSService(
        api_key=os.environ["CARTESIA_API_KEY"],
        settings=CartesiaHttpTTSService.Settings(
            voice="71a7ad14-091c-4e8e-a314-022ece01c121"
        )
    )

    # Create context and aggregators
    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            user_turn_strategies=UserTurnStrategies(
                stop=[SpeechTimeoutUserTurnStopStrategy()]
            )
        )
    )

    # Create debug processors
    debug1 = DebugProcessor("PostSTT")
    debug2 = DebugProcessor("PostLLM")
    debug3 = DebugProcessor("PostAggregator")
    debug4 = DebugProcessor("PreTTS")

    logger.info("Testing pipeline configurations...")
    logger.info("-" * 40)

    # Test 1: Basic pipeline (like local_bot.py)
    logger.info("\n1. BASIC PIPELINE (no aggregator)")
    pipeline1 = Pipeline([
        transport.input(),
        stt,
        debug1,
        user_aggregator,
        llm,
        debug2,
        tts,
        transport.output(),
        assistant_aggregator,
    ])

    # Test 2: Pipeline with LLMFullResponseAggregator
    logger.info("\n2. PIPELINE WITH AGGREGATOR")
    pipeline2 = Pipeline([
        transport.input(),
        stt,
        debug1,
        user_aggregator,
        llm,
        LLMFullResponseAggregator(),
        debug3,
        tts,
        transport.output(),
        assistant_aggregator,
    ])

    # Test 3: Pipeline with aggregator in different position
    logger.info("\n3. PIPELINE WITH AGGREGATOR AFTER TTS")
    pipeline3 = Pipeline([
        transport.input(),
        stt,
        debug1,
        user_aggregator,
        llm,
        debug2,
        tts,
        LLMFullResponseAggregator(),
        debug3,
        transport.output(),
        assistant_aggregator,
    ])

    # Choose which pipeline to test
    pipeline_choice = 2  # Change this to test different configurations

    if pipeline_choice == 1:
        pipeline = pipeline1
        logger.info("Using BASIC pipeline")
    elif pipeline_choice == 2:
        pipeline = pipeline2
        logger.info("Using AGGREGATOR pipeline")
    else:
        pipeline = pipeline3
        logger.info("Using AGGREGATOR AFTER TTS pipeline")

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        )
    )

    # Set up runner
    from pipecat.workers.runner import WorkerRunner
    runner = WorkerRunner(handle_sigint=True)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected - ready for testing")
        logger.info("Speak into your microphone to test STT -> LLM -> TTS flow")

    await runner.add_workers(worker)

    # Run for 30 seconds
    logger.info("\n" + "=" * 60)
    logger.info("Pipeline running - speak to test")
    logger.info("Will auto-stop in 30 seconds...")
    logger.info("=" * 60)

    try:
        await asyncio.wait_for(runner.run(), timeout=30)
    except asyncio.TimeoutError:
        logger.info("\nTest completed - timeout reached")

    logger.info("\n" + "=" * 60)
    logger.info("RESULTS:")
    logger.info(f"PostSTT frames: {debug1.frame_count}")
    logger.info(f"PostLLM frames: {debug2.frame_count}")
    logger.info(f"PostAggregator frames: {debug3.frame_count}")
    logger.info(f"PreTTS frames: {debug4.frame_count}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_basic_pipeline())