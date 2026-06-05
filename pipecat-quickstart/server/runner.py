#
# AI-Recruiter: High-Fidelity Dashboard Server
# This script runs the Recruiter Bot and the FastAPI Dashboard Server.
#

import asyncio
import os
import sys
import json

from dotenv import load_dotenv
from loguru import logger
from livekit import api
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import SpeechTimeoutUserTurnStopStrategy
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport
from pipecat.workers.runner import WorkerRunner

# Import Recruiter-specific components
from bot import create_interview_session
from transcript_accumulator import TranscriptAccumulator
from question_flow_processor import QuestionFlowProcessor
from events.broadcaster import broadcaster
from llm.json_parser import LLMResponseParser
from core.metrics import MetricsTracker

load_dotenv(override=True)

try:
    logger.remove(0)
except Exception:
    pass
logger.add(sys.stderr, level="DEBUG")

# --- Global State ---
current_session = create_interview_session()
bot_worker = None
bot_ready = asyncio.Event()

# --- FastAPI App ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def index():
    return FileResponse("index.html")

@app.get("/health")
async def health():
    return {
        "status": "ready" if bot_ready.is_set() else "initializing",
        "session": current_session.session_id if current_session else "none"
    }

@app.get("/token")
async def get_token():
    # Wait for bot to be fully ready before issuing tokens to clients
    try:
        await asyncio.wait_for(bot_ready.wait(), timeout=15.0)
    except asyncio.TimeoutError:
        return {"error": "Bot initialization timed out. Check server logs."}

    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    room_name = os.getenv("LIVEKIT_ROOM_NAME", "test-room")
    
    token = (
        api.AccessToken(api_key, api_secret)
        .with_identity("candidate-user")
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )
    return {"token": token, "url": os.getenv("LIVEKIT_URL")}

@app.get("/events")
async def sse_events():
    """Streaming endpoint for dashboard updates."""
    queue = await broadcaster.subscribe()
    async def event_generator():
        try:
            while True:
                message = await queue.get()
                yield message
        except asyncio.CancelledError:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/session")
async def get_session():
    """Returns the full state of the current interview session."""
    if current_session:
        return {
            "session_id": current_session.session_id,
            "status": current_session.status.value,
            "config": {
                "job_role": current_session.config.job_role,
                "company_name": current_session.config.company_name,
                "system_prompt": current_session.config.system_prompt,
                "goals": [g.label for g in current_session.config.goals]
            },
            "transcript": [vars(t) for t in current_session.transcript],
            "evaluations": current_session.evaluations,
            "metrics": current_session.metrics,
            "goal_coverage": current_session.get_goal_coverage()
        }
    return {"error": "No active session"}

@app.post("/settings")
async def update_settings(request: Request):
    """Updates session persistence and timeout settings."""
    settings = await request.json()
    if current_session:
        timeout = settings.get("timeout", 300)
        auto_kill = settings.get("auto_kill", False)
        current_session.update_settings(timeout, auto_kill)
        return {"status": "success"}
    return {"error": "No active session"}

@app.post("/chat")
async def manual_chat(request: Request):
    """Handles manual text messages from the dashboard."""
    data = await request.json()
    text = data.get("text", "").strip()
    if text and current_session:
        current_session.add_turn(speaker="candidate", text=text)
        await broadcaster.broadcast("transcript", {"speaker": "candidate", "text": text})
        return {"status": "received"}
    return {"error": "No active session or empty text"}

# --- Bot Runner ---
async def run_bot():
    global bot_worker, current_session, bot_ready
    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    room_name = os.getenv("LIVEKIT_ROOM_NAME", "test-room")

    if not url or not api_key or not api_secret:
        logger.error("LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET must be set in .env")
        return

    # 1. Start Session
    current_session.start()

    # 2. Setup Transport
    token = (
        api.AccessToken(api_key, api_secret)
        .with_identity("recruiter-bot")
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )

    transport = LiveKitTransport(
        url=url,
        token=token,
        room_name=room_name,
        params=LiveKitParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
    )

    # 3. Setup Services
    stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"])
    llm = GroqLLMService(
        api_key=os.environ["GROQ_API_KEY"],
        settings=GroqLLMService.Settings(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            system_instruction=current_session.config.system_prompt,
        ),
    )
    tts = CartesiaTTSService(
        api_key=os.environ["CARTESIA_API_KEY"],
        settings=CartesiaTTSService.Settings(
            voice=os.getenv("CARTESIA_VOICE_ID", "71a7ad14-091c-4e8e-a314-022ece01c121"),
        ),
    )

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            user_turn_strategies=UserTurnStrategies(
                stop=[SpeechTimeoutUserTurnStopStrategy()]
            )
        ),
    )

    # 4. Dashboard Processors
    transcript_accumulator = TranscriptAccumulator(current_session, broadcaster)
    question_flow = QuestionFlowProcessor(current_session, context)
    response_parser = LLMResponseParser(current_session, broadcaster)
    metrics_tracker = MetricsTracker(current_session, broadcaster)

    # 5. Build Pipeline
    pipeline = Pipeline([
        transport.input(),
        stt,
        transcript_accumulator,
        user_aggregator,
        question_flow,
        llm,
        assistant_aggregator,
        response_parser,
        tts,
        transport.output(),
        metrics_tracker,
    ])

    bot_worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
    )

    # 6. Event Handlers
    @transport.event_handler("on_participant_connected")
    async def on_participant_connected(transport, participant):
        identity = getattr(participant, "identity", participant)
        logger.info(f"UI Joined Room: {identity}")
        await broadcaster.broadcast("participant", {"event": "joined", "identity": identity})

    @transport.event_handler("on_participant_disconnected")
    async def on_participant_disconnected(transport, participant):
        identity = getattr(participant, "identity", participant)
        logger.info(f"UI Left Room: {identity}")
        await broadcaster.broadcast("participant", {"event": "dropped", "identity": identity})
        if current_session.auto_kill_on_disconnect:
            await bot_worker.cancel()

    # Manual Status Hooks
    async def push_status():
        await asyncio.sleep(2)
        await broadcaster.broadcast("service", {"name": "STT", "status": "connected"})
        await broadcaster.broadcast("service", {"name": "LLM", "status": "connected"})
        await broadcaster.broadcast("service", {"name": "TTS", "status": "connected"})
        await broadcaster.broadcast("status", {"status": "ready"})
    
    asyncio.create_task(push_status())

    runner = WorkerRunner(handle_sigint=True)
    await runner.add_workers(bot_worker)
    
    logger.info(f"🚀 Bot attempting to join Room: {room_name}")
    try:
        bot_ready.set()
        await runner.run()
    except Exception as e:
        logger.error(f"Bot failed to run: {e}")
        await broadcaster.broadcast("status", {"status": "error", "message": str(e)})

async def main():
    config = uvicorn.Config(app, host="127.0.0.1", port=7860, log_level="info")
    server = uvicorn.Server(config)
    
    await asyncio.gather(
        server.serve(),
        run_bot()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
