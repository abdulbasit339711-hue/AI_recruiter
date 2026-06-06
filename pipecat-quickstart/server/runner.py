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
from pipecat.services.cartesia.tts import CartesiaHttpTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport
from pipecat.workers.runner import WorkerRunner

# Import Recruiter-specific components
from bot_manager_dual import BotManager
from events.broadcaster import broadcaster

load_dotenv(override=True)

try:
    logger.remove(0)
except Exception:
    pass
logger.add(sys.stderr, level="DEBUG")

# --- Global State ---
bot_manager = None
bot_ready = asyncio.Event()
pipeline_mode = os.getenv("PIPELINE_MODE", "single")  # Default to single, can be set to "dual"

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
        "session": bot_manager.session.session_id if bot_manager else "none",
        "services": {
            "STT": "connected",
            "LLM": "connected",
            "TTS": "connected"
        }
    }

@app.get("/token")
async def get_token():
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
    queue = await broadcaster.subscribe()
    logger.debug("Client subscribed to events stream")
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
    if bot_manager and bot_manager.session:
        session = bot_manager.session
        return {
            "session_id": session.session_id,
            "status": session.status.value,
            "config": {
                "job_role": session.config.job_role,
                "company_name": session.config.company_name,
                "system_prompt": session.config.system_prompt,
                "goals": [g.label for g in session.config.goals]
            },
            "transcript": [{"speaker": t.speaker, "text": t.text} for t in session.transcript],
            "evaluations": session.evaluations,
            "metrics": session.metrics,
            "goal_coverage": session.get_goal_coverage()
        }
    return {"error": "No active session"}

@app.post("/settings")
async def update_settings(request: Request):
    settings = await request.json()
    if bot_manager and bot_manager.session:
        timeout = settings.get("timeout", 300)
        auto_kill = settings.get("auto_kill", False)
        # Set auto_kill on disconnect
        if auto_kill:
            logger.info("[Settings] Auto-kill requested, terminating session")
            bot_manager.session.auto_kill_on_disconnect = True
            # Cancel the worker to end the session
            if hasattr(bot_manager, 'worker'):
                await bot_manager.worker.cancel()
        return {"status": "success"}
    return {"error": "No active session"}

@app.post("/chat")
async def manual_chat(request: Request):
    data = await request.json()
    text = data.get("text", "").strip()
    if text and bot_manager:
        logger.info(f"[API] Manual chat input: {text}")
        await bot_manager.inject_text(text)
        return {"status": "received"}
    return {"error": "No active session or bot"}

@app.get("/pipeline")
async def get_pipeline():
    """Get current pipeline configuration"""
    if bot_manager:
        return bot_manager.get_pipeline_info()
    return {"mode": pipeline_mode, "status": "not_started"}

@app.post("/pipeline")
async def set_pipeline(request: Request):
    """Set pipeline mode (single or dual)"""
    global pipeline_mode
    data = await request.json()
    mode = data.get("mode", "single")

    if mode not in ["single", "dual"]:
        return {"error": "Invalid mode. Use 'single' or 'dual'"}

    pipeline_mode = mode
    logger.info(f"[API] Pipeline mode set to: {mode}")

    # Broadcast mode change
    await broadcaster.broadcast("pipeline_mode", {
        "mode": mode,
        "description": "Dual LLM (Judge + Responder)" if mode == "dual" else "Single LLM"
    })

    return {"mode": mode, "status": "updated", "restart_required": bot_manager is not None}

# --- Bot Runner ---
async def run_bot():
    global bot_manager, bot_ready
    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    room_name = os.getenv("LIVEKIT_ROOM_NAME", "test-room")

    if not url or not api_key or not api_secret:
        logger.error("LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET must be set in .env")
        return

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

    stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"])
    
    # Create session first to get the correct system prompt
    from bot import create_interview_session
    temp_session = create_interview_session()

    llm = GroqLLMService(
        api_key=os.environ["GROQ_API_KEY"],
        settings=GroqLLMService.Settings(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            system_instruction=temp_session.config.system_prompt,
        ),
    )
    tts = CartesiaHttpTTSService(
        api_key=os.environ["CARTESIA_API_KEY"],
        settings=CartesiaHttpTTSService.Settings(
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
    
    bot_manager = BotManager(transport, stt, llm, tts, context, user_aggregator, assistant_aggregator, mode=pipeline_mode)

    # Event Handlers
    @transport.event_handler("on_participant_connected")
    async def on_participant_connected(transport, participant):
        identity = getattr(participant, "identity", participant)
        logger.info(f"UI Joined Room: {identity}")
        await broadcaster.broadcast("participant", {"event": "joined", "identity": identity})

        # Send initial greeting when any participant joins (not the bot itself)
        if str(identity) != "recruiter-bot":
            await asyncio.sleep(2)  # Small delay to ensure pipeline is ready
            logger.info(f"[Bot] Sending initial greeting to participant: {identity}")

            # Add a greeting message to context to trigger LLM response
            context.add_message({
                "role": "user",
                "content": "[System: Candidate has joined. Please greet them warmly and start the interview.]"
            })

            # Trigger LLM to generate response
            from pipecat.frames.frames import LLMMessagesUpdateFrame
            await bot_manager.pipeline.push_frame(LLMMessagesUpdateFrame(messages=[], run_llm=True))

    @transport.event_handler("on_participant_disconnected")
    async def on_participant_disconnected(transport, participant):
        identity = getattr(participant, "identity", participant)
        logger.info(f"UI Left Room: {identity}")
        await broadcaster.broadcast("participant", {"event": "dropped", "identity": identity})
        if bot_manager.session.auto_kill_on_disconnect:
            await bot_manager.worker.cancel()

    async def push_status():
        await asyncio.sleep(2)
        await broadcaster.broadcast("status", {"status": "ready"})
        # Proactively tell dashboard services are "online"
        await broadcaster.broadcast("service", {"name": "STT", "status": "connected"})
        await broadcaster.broadcast("service", {"name": "LLM", "status": "connected"})
        await broadcaster.broadcast("service", {"name": "TTS", "status": "connected"})
    
    asyncio.create_task(push_status())
    
    # Explicitly start
    await bot_manager.start()
    
    runner = WorkerRunner(handle_sigint=True)
    await runner.add_workers(bot_manager.worker)
    
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
