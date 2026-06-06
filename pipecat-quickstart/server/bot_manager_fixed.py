import asyncio
import os
from loguru import logger
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker, PipelineParams
from pipecat.frames.frames import StartFrame, TranscriptionFrame, TextFrame, LLMFullResponseEndFrame
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.processors.aggregators.llm_response import LLMFullResponseAggregator
from bot import create_interview_session
from transcript_accumulator import TranscriptAccumulator
from question_flow_processor import QuestionFlowProcessor
from events.broadcaster import broadcaster
from audio_debug import AudioDebugger, AudioPipelineValidator
import json
import re

logger.info(f"Broadcaster imported successfully: {broadcaster}")


class CombinedResponseHandler(FrameProcessor):
    """
    Handles both response parsing and metrics in one place
    """
    def __init__(self, session, broadcaster):
        super().__init__()
        self._session = session
        self._broadcaster = broadcaster
        self._buffer = []
        self._total_tokens = 0

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)

        # Buffer text frames
        if isinstance(frame, TextFrame):
            self._buffer.append(frame.text)
            # Pass through for TTS
            await self.push_frame(frame, direction)
            return

        # Handle aggregated response
        elif isinstance(frame, LLMFullResponseEndFrame):
            logger.info("[CombinedHandler] Processing LLMFullResponseEndFrame")

            # Get complete text
            full_text = getattr(frame, 'text', '')
            if not full_text and self._buffer:
                full_text = ''.join(self._buffer)
            self._buffer = []

            # Parse response
            if full_text:
                try:
                    # Try to extract JSON
                    json_match = re.search(r'(\{.*\})', full_text, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group(1))
                        response_text = data.get("response", full_text)
                        evaluation = data.get("evaluation", {})

                        # Broadcast evaluation
                        if evaluation:
                            await self._broadcaster.broadcast("evaluation", {
                                "session_id": self._session.session_id,
                                "data": evaluation
                            })
                    else:
                        response_text = full_text
                except:
                    response_text = full_text

                # Add and broadcast agent transcript
                logger.info(f"[CombinedHandler] Agent says: {response_text[:100]}...")
                self._session.add_turn(
                    speaker="agent",
                    text=response_text,
                    question_id=self._session.current_question.id if self._session.current_question else None
                )

                await self._broadcaster.broadcast("transcript", {
                    "speaker": "agent",
                    "text": response_text
                })

            # Handle metrics
            usage = getattr(frame, 'usage', None)
            if usage:
                prompt_tokens = getattr(usage, 'prompt_tokens', 0)
                completion_tokens = getattr(usage, 'completion_tokens', 0)
                total_tokens = getattr(usage, 'total_tokens', 0)

                self._total_tokens += total_tokens

                logger.info(f"[CombinedHandler] Metrics - Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}, Session: {self._total_tokens}")

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
                logger.warning("[CombinedHandler] No usage metrics in frame")

            # Pass frame through
            await self.push_frame(frame, direction)

        else:
            # Pass all other frames
            await self.push_frame(frame, direction)


class BotManager:
    def __init__(self, transport, stt, llm, tts, context, user_aggregator, assistant_aggregator):
        self.transport = transport
        self.session = create_interview_session()
        self.session.start()
        self.session.auto_kill_on_disconnect = False  # Initialize the attribute

        # Validate audio configuration
        AudioPipelineValidator.validate_transport(transport)
        AudioPipelineValidator.validate_services(stt, tts, llm)

        transcript_accumulator = TranscriptAccumulator(self.session, broadcaster)
        self.question_flow = QuestionFlowProcessor(self.session, context)
        combined_handler = CombinedResponseHandler(self.session, broadcaster)

        logger.info("[BotManager] Building pipeline with combined handler")

        # Simplified, correct pipeline
        pipeline_components = [
            self.transport.input(),
            stt,
            transcript_accumulator,
            user_aggregator,
            self.question_flow,
            llm,
            LLMFullResponseAggregator(),  # This adds usage metrics to the frame
            combined_handler,              # Handle both transcripts and metrics
            tts,
            self.transport.output(),
            assistant_aggregator,
        ]

        # Add audio debugging if enabled
        if os.getenv("DEBUG_MODE", "false").lower() == "true":
            logger.info("[BotManager] Audio debugging enabled")
            pipeline_components.insert(2, AudioDebugger("PostSTT"))
            pipeline_components.insert(-3, AudioDebugger("PreTTS"))

        self.pipeline = Pipeline(pipeline_components)

        self.worker = PipelineWorker(
            self.pipeline,
            params=PipelineParams(
                enable_metrics=True,
                enable_usage_metrics=True,
                send_initial_empty_metrics=False,
            ),
        )

    async def start(self):
        logger.info("[BotManager] Starting bot session")
        # The worker will handle pushing the StartFrame
        pass

    async def inject_text(self, text, user_id="candidate"):
        frame = TranscriptionFrame(text=text, user_id=user_id, timestamp="100")
        logger.info(f"[BotManager] Injecting text: {text}")
        await self.transport.input().push_frame(frame)