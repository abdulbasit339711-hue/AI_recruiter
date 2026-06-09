#
# AI-Recruiter: High-Fidelity Dashboard Server
# This script runs the Recruiter Bot and the FastAPI Dashboard Server.
#

import asyncio
import logging
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
from resilient_tts import ResilientCartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport
from pipecat.workers.runner import WorkerRunner

# Load .env BEFORE importing local modules: database.py builds its global
# db_manager (reading DB_* env vars) at import time, so .env must be loaded first
# or it falls back to the default postgres/empty-password and auth fails.
load_dotenv(override=True)

# Import Recruiter-specific components
from bot_manager_dual import BotManager
from events.broadcaster import broadcaster

try:
    logger.remove()  # remove ALL existing sinks (default + any pipecat added) so our
                     # single filtered sink below is authoritative — this also fixes the
                     # duplicate "every line logged twice" output.
except Exception:
    pass


# Deepgram's STT connection idle-closes (code 1011) when no audio is flowing —
# e.g. while testing the conversation via the dashboard /chat box with no mic, or
# while the bot is speaking. Those closes are NON-FATAL: Deepgram auto-reconnects.
# They just flood the logs. Suppress that specific, self-healing noise so text
# testing is clean, while leaving genuine STT errors visible. This is automatic;
# nothing to configure.
_STT_IDLE_NOISE = (
    "did not receive audio",
    "keepalive ping timeout",
    "Keepalive failed",
    "send_media failed, connection will reconnect",
    "connection error, will retry",
    "Connection lost, will retry",
)


def _suppress_idle_stt_noise(record) -> bool:
    msg = record["message"]
    return not any(s in msg for s in _STT_IDLE_NOISE)


logger.add(sys.stderr, level="DEBUG", filter=_suppress_idle_stt_noise)

# The Deepgram SDK uses websockets' DEPRECATED legacy client, which logs benign
# teardown tracebacks ("keepalive ping failed" / "data transfer failed" with an
# AssertionError from _drain_helper) via the stdlib logging module whenever a
# connection drops (e.g. idle STT, or a network blip). These are non-fatal noise.
# websockets is already at the latest (16.0) — the bug lives in the legacy module
# itself — so we silence that stdlib logger. Genuine STT errors still surface via
# pipecat's own (loguru) logging. (Note: LiveKit's Rust SDK logs print directly to
# stderr and cannot be filtered from Python.)
logging.getLogger("websockets").setLevel(logging.CRITICAL)

# --- Global State ---
bot_manager = None
bot_ready = asyncio.Event()
pipeline_mode = os.getenv("PIPELINE_MODE", "single")  # Default to single, can be set to "dual"

# The (candidate_id, job_id) for the NEXT interview to configure on connect.
# Set via POST /interview/configure (Phase 3 will set it from a validated token),
# or via INTERVIEW_CANDIDATE_ID / INTERVIEW_JOB_ID env for local dev.
pending_interview = {
    "candidate_id": (int(os.getenv("INTERVIEW_CANDIDATE_ID")) if os.getenv("INTERVIEW_CANDIDATE_ID") else None),
    "job_id": (int(os.getenv("INTERVIEW_JOB_ID")) if os.getenv("INTERVIEW_JOB_ID") else None),
}

# Tracks the DEFAULT (dashboard/testing) bot's lifecycle so /health can report the
# truth instead of a hardcoded "everything's fine".
bot_state: dict = {"error": None}
_bot_task: "asyncio.Task | None" = None

# --- Per-interview bot registry (room-per-interview isolation) ---
# Each REAL interview runs in its OWN LiveKit room with its OWN bot, configured
# up-front from the token's (candidate_id, job_id) — so concurrent candidates can
# never share a room or clobber each other's session (the old single "test-room" +
# global pending_interview race). The default bot above is only for the dashboard.
DEFAULT_ROOM = os.getenv("LIVEKIT_ROOM_NAME", "test-room")
START_DEFAULT_BOT = (os.getenv("START_DEFAULT_BOT", "true").strip().lower() in ("1", "true", "yes", "on"))
MAX_CONCURRENT_INTERVIEWS = int(os.getenv("MAX_CONCURRENT_INTERVIEWS", "3"))
_interviews: dict = {}                      # room_name -> InterviewBot
_interviews_lock = asyncio.Lock()
_shutting_down = False


class InterviewBot:
    """A single live interview: its own room, bot manager, and worker task."""
    def __init__(self, room_name: str, candidate_id: int, job_id: int):
        self.room_name = room_name
        self.candidate_id = candidate_id
        self.job_id = job_id
        self.manager = None
        self.session_id = None
        self.error = None
        self.ready = asyncio.Event()
        self.task: "asyncio.Task | None" = None

# --- FastAPI App ---
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """ASGI startup/shutdown.

    Starts a supervised DEFAULT bot (for the :7860 testing dashboard) that respawns
    if it idles out. REAL interviews are started on demand per room by
    ``ensure_interview`` (called from /interview/validate). Started here so any
    launcher (uvicorn runner:app, gunicorn, container CMD) boots the full system.
    """
    global _bot_task, _shutting_down
    _shutting_down = False
    if START_DEFAULT_BOT:
        _bot_task = asyncio.create_task(_supervise_default_bot())
    try:
        yield
    finally:
        _shutting_down = True
        tasks = []
        if _bot_task and not _bot_task.done():
            _bot_task.cancel()
            tasks.append(_bot_task)
        async with _interviews_lock:
            for b in _interviews.values():
                if b.task and not b.task.done():
                    b.task.cancel()
                    tasks.append(b.task)
        for t in tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass
        # Close the DB pool on shutdown (was previously leaked).
        try:
            from database import db_manager
            await db_manager.close()
        except Exception:
            pass


app = FastAPI(lifespan=lifespan)

import hmac
from fastapi.responses import JSONResponse

# The voice service (:7860) is a local TESTING + bot-runtime component. Its
# operator endpoints (/chat, /settings, /pipeline, /interview/configure) are OPEN
# by default — no auth needed for testing. The real security boundary for
# applicants is the SIGNED INTERVIEW LINK, verified by /interview/validate.
#
# For an exposed/production deployment, set VOICE_REQUIRE_AUTH=true to require the
# shared admin bearer token on these operator endpoints.
_PROTECTED_VOICE_ROUTES = {
    ("POST", "/interview/configure"),
    ("POST", "/chat"),
    ("POST", "/settings"),
    ("POST", "/pipeline"),
}


def _voice_auth_required() -> bool:
    return (os.getenv("VOICE_REQUIRE_AUTH", "") or "").strip().lower() in ("1", "true", "yes", "on")


def _voice_token_ok(authorization: str | None) -> bool:
    expected = (os.getenv("ADMIN_API_TOKEN") or "").strip()
    if not expected or not authorization:
        return False
    scheme, _, presented = authorization.partition(" ")
    return scheme.lower() == "bearer" and bool(presented) and hmac.compare_digest(presented.strip(), expected)


@app.middleware("http")
async def voice_admin_guard(request: Request, call_next):
    # Off by default (testing). Only enforced when VOICE_REQUIRE_AUTH is set.
    if _voice_auth_required() and (request.method, request.url.path) in _PROTECTED_VOICE_ROUTES:
        if not _voice_token_ok(request.headers.get("authorization")):
            return JSONResponse(status_code=401, content={"error": "missing or invalid operator credentials"})
    return await call_next(request)


# Explicit origin allowlist instead of "*". Added after the auth guard so CORS is
# the outermost middleware (401/503 responses still carry CORS headers).
_voice_cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_voice_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.get("/")
async def index():
    return FileResponse("index.html")

@app.get("/health")
async def health():
    err = bot_state.get("error")
    default_running = _bot_task is not None and not _bot_task.done()
    default_ready = bot_ready.is_set() and bot_manager is not None and err is None
    # Healthy if the default bot is ready OR a real interview is running, or if the
    # default bot is intentionally disabled.
    if err and not _interviews:
        status = "error"
    elif default_ready or _interviews or not START_DEFAULT_BOT:
        status = "ready"
    else:
        status = "initializing"
    svc = "connected" if default_ready else ("error" if err else "initializing")
    return {
        "status": status,
        "default_bot_running": default_running,
        "active_interviews": len(_interviews),
        "max_concurrent_interviews": MAX_CONCURRENT_INTERVIEWS,
        "error": err,
        "default_room": DEFAULT_ROOM,
        "session": bot_manager.session.session_id if (bot_manager and bot_manager.session) else "none",
        "services": {"STT": svc, "LLM": svc, "TTS": svc},
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

@app.get("/interview/validate")
async def validate_interview(token: str):
    """Validate a candidate's emailed interview link and return join credentials.

    On success, records which (candidate, job) this interview is for so the session
    is configured when the candidate joins, and returns LiveKit credentials.
    """
    from recruiter_shared import verify_invite_token, InviteTokenError
    from database import db_manager

    secret = os.getenv("INTERVIEW_LINK_SECRET")
    if not secret:
        return {"valid": False, "error": "interview links not configured on server"}
    try:
        claims = verify_invite_token(token, secret)
    except InviteTokenError as e:
        return {"valid": False, "error": f"This interview link is invalid or has expired ({e})."}

    # Unique room per interview link (jti makes it unique). Spin up a dedicated bot
    # bound to THIS candidate/job — no shared room, no global state, no cross-talk.
    room = f"interview-{claims.candidate_id}-{claims.jti[:12]}"
    bot = await ensure_interview(claims.candidate_id, claims.job_id, room)
    if bot is None:
        return {
            "valid": False,
            "error": "All interview slots are currently busy. Please try again in a few minutes.",
        }
    if bot.error:
        return {"valid": False, "error": "Could not start the interview. Please contact the recruiter."}

    try:
        await db_manager._ensure_pool()
        job = await db_manager.get_job(claims.job_id)
        candidate = await db_manager.get_candidate(claims.candidate_id)
    except Exception as e:
        logger.error(f"[Interview] validate lookup failed: {e}")
        job, candidate = None, None

    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    lk_token = (
        api.AccessToken(api_key, api_secret)
        .with_identity(f"candidate-{claims.candidate_id}")
        .with_grants(api.VideoGrants(room_join=True, room=room))
        .to_jwt()
    )
    return {
        "valid": True,
        "candidate_name": (candidate or {}).get("name"),
        "job_title": (job or {}).get("title"),
        "room_name": room,
        "session_id": bot.session_id,  # lets the client filter the live event stream
        "livekit_token": lk_token,
        "livekit_url": os.getenv("LIVEKIT_URL"),
    }

@app.get("/events")
async def sse_events(session: str | None = None):
    # `session` scopes the stream to one interview (candidate page passes its
    # session_id); omitted = unfiltered (dashboard sees all).
    queue = await broadcaster.subscribe(session)
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
        session_data = {
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

        # Add goal tracking information if available
        if bot_manager.goal_service:
            try:
                goal_progress = await bot_manager.get_goal_progress()
                session_data["goal_tracking"] = {
                    "enabled": True,
                    "progress": goal_progress
                }
            except Exception as e:
                logger.warning(f"[API] Failed to get goal progress: {e}")
                session_data["goal_tracking"] = {
                    "enabled": True,
                    "error": str(e)
                }
        else:
            session_data["goal_tracking"] = {"enabled": False}

        return session_data
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
    session = data.get("session")
    if not text:
        return {"error": "no text provided"}
    # Route to the candidate's OWN interview bot when a session is given (the
    # candidate call page passes its session_id); otherwise fall back to the
    # default dashboard bot.
    target = None
    if session:
        for b in _interviews.values():
            if b.session_id == session and b.manager:
                target = b.manager
                break
        if target is None:
            return {"error": "interview not found or already ended"}
    else:
        target = bot_manager
    if target is None:
        return {"error": "No active session or bot"}
    logger.info(f"[API] Manual chat input (session={session or 'default'}): {text}")
    await target.inject_text(text)
    return {"status": "received"}

@app.post("/interview/configure")
async def configure_interview(request: Request):
    """Select which candidate+job the next interview is for, and configure it now.

    Phase 3 will drive this from a validated interview-link token; for now it can
    be called directly (or set via INTERVIEW_* env). Configures the running
    BotManager immediately so /session reflects the chosen job/role.
    """
    data = await request.json()
    try:
        candidate_id = int(data["candidate_id"])
        job_id = int(data["job_id"])
    except (KeyError, ValueError, TypeError):
        return {"error": "candidate_id and job_id (integers) are required"}

    pending_interview["candidate_id"] = candidate_id
    pending_interview["job_id"] = job_id

    if not bot_manager:
        return {"status": "pending", "detail": "stored; bot not started yet"}

    try:
        from session_factory import create_session_for
        session = await create_session_for(candidate_id, job_id)
        await bot_manager.configure_session(session)
        return {
            "status": "configured",
            "session_id": session.session_id,
            "job_role": session.config.job_role,
            "candidate_name": session.candidate_name,
        }
    except Exception as e:
        logger.error(f"[API] Failed to configure interview: {e}")
        return JSONResponse(status_code=500, content={"error": "failed to configure interview"})

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

# --- Goal Tracking Endpoints ---
@app.get("/goals/{session_id}")
async def get_goals(session_id: str):
    """Get goal progress for a session"""
    if not bot_manager or not bot_manager.goal_service:
        return {"error": "Goal tracking not enabled"}

    try:
        goals = await bot_manager.goal_service.get_session_goals(session_id)
        progress = await bot_manager.goal_service.get_goal_progress_summary(session_id)
        return {
            "session_id": session_id,
            "goals": goals,
            "summary": progress
        }
    except Exception as e:
        logger.error(f"[API] Failed to get goals: {e}")
        return {"error": str(e)}

@app.get("/goals")
async def get_current_goals():
    """Get goal progress for current session"""
    if not bot_manager or not bot_manager.goal_service:
        return {"error": "Goal tracking not enabled"}

    try:
        session_id = bot_manager.session.session_id
        return await bot_manager.get_goal_progress()
    except Exception as e:
        logger.error(f"[API] Failed to get current goals: {e}")
        return {"error": str(e)}

@app.post("/goals/{session_id}/manual-update")
async def manual_goal_update(session_id: str, request: Request):
    """Manually update goal progress"""
    if not bot_manager or not bot_manager.goal_service:
        return {"error": "Goal tracking not enabled"}

    try:
        data = await request.json()
        goal_title = data.get("goal_title")
        update_data = data.get("update_data", {})

        if not goal_title:
            return {"error": "goal_title is required"}

        success = await bot_manager.goal_service.manual_goal_update(
            session_id, goal_title, update_data
        )

        if success:
            # Broadcast update
            await broadcaster.broadcast("manual_goal_update", {
                "session_id": session_id,
                "goal_title": goal_title,
                "update_data": update_data
            })
            return {"status": "updated"}
        else:
            return {"error": "Update failed"}

    except Exception as e:
        logger.error(f"[API] Manual goal update failed: {e}")
        return {"error": str(e)}

@app.get("/goals/suggest-question")
async def suggest_question():
    """Get adaptive question suggestion based on goal progress"""
    if not bot_manager:
        return {"error": "No active session"}

    try:
        suggestion = await bot_manager.get_adaptive_question_suggestion()
        return {"suggestion": suggestion}
    except Exception as e:
        logger.error(f"[API] Failed to get question suggestion: {e}")
        return {"error": str(e)}

@app.post("/goals/{session_id}/analyze")
async def comprehensive_analysis(session_id: str):
    """Perform comprehensive goal analysis"""
    if not bot_manager or not bot_manager.goal_service:
        return {"error": "Goal tracking not enabled"}

    try:
        analysis = await bot_manager.goal_service.comprehensive_goal_analysis(session_id)
        return analysis
    except Exception as e:
        logger.error(f"[API] Comprehensive analysis failed: {e}")
        return {"error": str(e)}

@app.post("/goals/templates")
async def create_goal_template(request: Request):
    """Create a new goal template"""
    if not bot_manager or not bot_manager.goal_service:
        return {"error": "Goal tracking not enabled"}

    try:
        template_data = await request.json()

        # Validate required fields
        required_fields = ["role_type", "category", "title", "description"]
        for field in required_fields:
            if field not in template_data:
                return {"error": f"Missing required field: {field}"}

        # Add to database via service
        from database import db_manager
        query = """
        INSERT INTO goal_templates
        (role_type, category, title, description, success_criteria, priority_weight, estimated_time_minutes, question_templates)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
        """

        template_id = await db_manager.execute_query(
            query,
            template_data["role_type"],
            template_data["category"],
            template_data["title"],
            template_data["description"],
            json.dumps(template_data.get("success_criteria", [])),
            template_data.get("priority_weight", 1.0),
            template_data.get("estimated_time_minutes", 5),
            json.dumps(template_data.get("question_templates", []))
        )

        return {"template_id": template_id, "status": "created"}

    except Exception as e:
        logger.error(f"[API] Failed to create goal template: {e}")
        return {"error": str(e)}

@app.get("/goals/templates/{role_type}")
async def get_goal_templates(role_type: str):
    """Get goal templates for a role type"""
    if not bot_manager or not bot_manager.goal_service:
        return {"error": "Goal tracking not enabled"}

    try:
        from database import db_manager
        templates = await db_manager.get_goal_templates(role_type)
        return {"templates": templates}
    except Exception as e:
        logger.error(f"[API] Failed to get templates: {e}")
        return {"error": str(e)}

# --- Bot runner (one bot per room) ---
async def _make_and_run_bot(room_name, candidate_id, job_id, *, is_default, bot_ref=None):
    """Build a LiveKit bot bound to ONE room (+ optionally one candidate/job) and
    run its worker until it ends (disconnect / idle / cancel).

    For REAL interviews the session is configured UP FRONT from (candidate_id,
    job_id), so there is no shared global state and no cross-candidate race.
    """
    global bot_manager
    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    if not url or not api_key or not api_secret:
        msg = "LiveKit credentials not configured (LIVEKIT_URL/API_KEY/API_SECRET)"
        logger.error(msg)
        if is_default:
            bot_state["error"] = msg
        if bot_ref:
            bot_ref.error = msg
            bot_ref.ready.set()
        return

    token = (
        api.AccessToken(api_key, api_secret)
        .with_identity("recruiter-bot")
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )
    transport = LiveKitTransport(
        url=url, token=token, room_name=room_name,
        params=LiveKitParams(audio_in_enabled=True, audio_out_enabled=True),
    )
    stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"])
    llm = GroqLLMService(
        api_key=os.environ["GROQ_API_KEY"],
        settings=GroqLLMService.Settings(model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")),
    )
    tts = ResilientCartesiaTTSService(
        api_key=os.environ["CARTESIA_API_KEY"],
        settings=ResilientCartesiaTTSService.Settings(
            voice=os.getenv("CARTESIA_VOICE_ID", "71a7ad14-091c-4e8e-a314-022ece01c121")),
    )
    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            user_turn_strategies=UserTurnStrategies(stop=[SpeechTimeoutUserTurnStopStrategy()])),
    )
    manager = BotManager(transport, stt, llm, tts, context, user_aggregator, assistant_aggregator, mode=pipeline_mode)
    if is_default:
        bot_manager = manager
    if bot_ref:
        bot_ref.manager = manager

    # Build the session UP FRONT so validate can return its session_id (for the SSE
    # filter) — but bound to THIS candidate/job, not global. We CONFIGURE it on
    # connect (below), once the pipeline is running, which is when the greeting
    # reliably triggers the LLM.
    pre_session = None
    if candidate_id and job_id:
        try:
            from session_factory import create_session_for
            pre_session = await create_session_for(candidate_id, job_id)
            if bot_ref:
                bot_ref.session_id = pre_session.session_id
        except Exception as e:
            logger.error(f"[Bot] Could not build interview session (candidate={candidate_id}, job={job_id}): {e}")
            if bot_ref:
                bot_ref.error = f"session build failed: {e}"

    # Greet exactly once, triggered by WHICHEVER fires first: the candidate's
    # participant-connected event OR their audio track being subscribed. The latter
    # covers the race where the candidate is already in the room when the bot
    # connects (then on_participant_connected never fires) — the bug that caused
    # intermittent "no greeting / no transcript".
    _greeted = {"done": False}

    async def _greet_once(identity):
        if _greeted["done"] or str(identity) == "recruiter-bot":
            return
        _greeted["done"] = True
        await asyncio.sleep(1.0)
        # Configure now (pipeline running, candidate page subscribed) — goals
        # broadcast to the live client at this point.
        if pre_session is not None and manager.session is None:
            try:
                await manager.configure_session(pre_session)
            except Exception as e:
                logger.error(f"[Bot] configure_session failed in {room_name}: {e}")
        logger.info(f"[Bot] Greeting participant in {room_name}: {identity}")
        # DETERMINISTIC, role-aware opener — reliable audio AND transcript (the old
        # LLMMessagesUpdateFrame trigger was flaky). The LLM drives the rest of the
        # conversation from the candidate's spoken answers.
        role = None
        if manager.session and getattr(manager.session, "config", None):
            role = getattr(manager.session.config, "job_role", None)
        greeting = (
            f"Hello, and welcome to your interview for {role}. " if role
            else "Hello, and welcome to your interview. "
        ) + (
            "I'm your AI interviewer. To get started, could you tell me a little "
            "about yourself and your background?"
        )
        sid = manager.session.session_id if manager.session else None
        await broadcaster.broadcast("transcript", {"session_id": sid, "speaker": "agent", "text": greeting})
        try:
            context.add_message({"role": "assistant", "content": greeting})
        except Exception:
            pass
        from pipecat.frames.frames import TTSSpeakFrame
        await manager.pipeline.push_frame(TTSSpeakFrame(greeting))

    @transport.event_handler("on_connected")
    async def on_connected(transport, *args):
        # Bot is now actually IN the room. Bind the session here (before the
        # candidate joins) so even an early message has the right session_id, and
        # only NOW mark ready — so validate waits until the bot is in the room and
        # the candidate never joins an empty room.
        logger.info(f"[Bot] Connected to room {room_name}")
        if pre_session is not None and manager.session is None:
            try:
                await manager.configure_session(pre_session)
            except Exception as e:
                logger.error(f"[Bot] configure_session failed in {room_name}: {e}")
        if is_default:
            bot_state["error"] = None
            bot_ready.set()
        if bot_ref:
            bot_ref.ready.set()

    @transport.event_handler("on_participant_connected")
    async def on_participant_connected(transport, participant):
        identity = getattr(participant, "identity", participant)
        logger.info(f"UI Joined Room {room_name}: {identity}")
        await broadcaster.broadcast("participant", {"event": "joined", "identity": str(identity)})
        await _greet_once(identity)

    @transport.event_handler("on_audio_track_subscribed")
    async def on_audio_track_subscribed(transport, participant, *rest):
        # Fires when the bot subscribes to the candidate's mic — covers the
        # already-present-on-connect race.
        identity = getattr(participant, "identity", participant)
        await _greet_once(identity)

    @transport.event_handler("on_participant_disconnected")
    async def on_participant_disconnected(transport, participant):
        identity = getattr(participant, "identity", participant)
        logger.info(f"UI Left Room {room_name}: {identity}")
        await broadcaster.broadcast("participant", {"event": "dropped", "identity": str(identity)})
        # End a REAL interview when the candidate leaves — frees the slot/room.
        if not is_default and str(identity) != "recruiter-bot":
            try:
                await manager.worker.cancel()
            except Exception:
                pass

    await manager.start()
    runner = WorkerRunner(handle_sigint=False)  # only the process owner handles signals
    await runner.add_workers(manager.worker)
    logger.info(f"🚀 Bot joining room {room_name} (candidate={candidate_id}, job={job_id})")
    # readiness is signalled from the on_connected handler (above), i.e. once the
    # bot is actually in the room — not here, where it has only started connecting.
    try:
        await runner.run()
    finally:
        # The worker has ended (disconnect / idle / cancel). Run the final goal
        # analysis and persist the assessment exactly once, for REAL interviews
        # only — the always-on default bot has no candidate/session to finalize.
        if not is_default:
            try:
                await manager.finalize_session()
            except Exception as e:
                logger.error(f"[Bot] finalize_session failed for {room_name}: {e}")


async def ensure_interview(candidate_id, job_id, room_name):
    """Get-or-spawn the dedicated bot for an interview room. Returns the
    InterviewBot, or None if the concurrency cap is reached."""
    async with _interviews_lock:
        existing = _interviews.get(room_name)
        if existing and existing.task and not existing.task.done():
            return existing
        # prune finished
        for rn in [rn for rn, b in _interviews.items() if b.task and b.task.done()]:
            _interviews.pop(rn, None)
        if len(_interviews) >= MAX_CONCURRENT_INTERVIEWS:
            logger.warning(f"[Interview] capacity reached ({MAX_CONCURRENT_INTERVIEWS}); refusing {room_name}")
            return None

        bot = InterviewBot(room_name, candidate_id, job_id)

        async def _runner():
            try:
                await _make_and_run_bot(room_name, candidate_id, job_id, is_default=False, bot_ref=bot)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"[Interview {room_name}] worker error: {e}")
                bot.error = str(e)
                bot.ready.set()
            finally:
                async with _interviews_lock:
                    _interviews.pop(room_name, None)
                logger.info(f"[Interview {room_name}] ended; slot freed ({len(_interviews)} active)")

        bot.task = asyncio.create_task(_runner())
        _interviews[room_name] = bot

    # Wait until the bot is actually IN the room (on_connected sets ready), so the
    # candidate joins to a present, configured bot — not an empty room. LiveKit
    # cold-connect can occasionally take ~20s, hence the generous timeout.
    try:
        await asyncio.wait_for(bot.ready.wait(), timeout=35.0)
    except asyncio.TimeoutError:
        logger.warning(f"[Interview {room_name}] bot not in room within 35s")
    return bot


async def _supervise_default_bot():
    """Keep a default-room bot alive for the :7860 testing dashboard, respawning it
    if it idles out — so the dashboard never shows a permanently dead bot."""
    backoff = 2
    while not _shutting_down:
        try:
            bot_ready.clear()
            await _make_and_run_bot(DEFAULT_ROOM, None, None, is_default=True)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[DefaultBot] stopped: {e}")
            bot_state["error"] = str(e)
        if _shutting_down:
            break
        logger.info(f"[DefaultBot] worker ended; respawning in {backoff}s")
        try:
            await asyncio.sleep(backoff)
        except asyncio.CancelledError:
            break


async def main():
    config = uvicorn.Config(app, host="127.0.0.1", port=7860, log_level="info")
    server = uvicorn.Server(config)
    # The bot worker is started by the app's lifespan, so `python runner.py` and
    # `uvicorn runner:app` behave identically. Here we just run the HTTP server.
    await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
