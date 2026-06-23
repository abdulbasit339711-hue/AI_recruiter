#
# AI-Recruiter: High-Fidelity Dashboard Server
# This script runs the Recruiter Bot and the FastAPI Dashboard Server.
#

import asyncio
import logging
import os
import re
import sys
import json
import threading

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
from pipecat.services.cartesia.tts import CartesiaHttpTTSService
from processors.resilient_tts import (
    ResilientCartesiaTTSService,
    ResilientDeepgramTTSService,
    ResilientDeepgramHttpTTSService,
)
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.groq.stt import GroqSTTService
from pipecat.transcriptions.language import Language
from pipecat.audio.filters.rnnoise_filter import RNNoiseFilter
from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport
from pipecat.workers.runner import WorkerRunner

# Load .env BEFORE importing local modules: database.py builds its global
# db_manager (reading DB_* env vars) at import time, so .env must be loaded first
# or it falls back to the default postgres/empty-password and auth fails.
load_dotenv(override=True)

# Import Recruiter-specific components
from bot_manager import (
    BotManager,
    DEEPGRAM_ENDPOINTING_MS,
    RECORD_VIDEO,
    build_user_turn_strategies,
)
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


logger.add(sys.stderr, level="DEBUG", filter=_suppress_idle_stt_noise, enqueue=True)

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
# aiohttp session for the HTTP TTS service (one request per utterance — far more
# robust than a persistent websocket on a flaky / resource-starved host). An
# aiohttp.ClientSession is bound to the loop it was created on, and each interview bot
# runs on its OWN loop in a dedicated thread, so we keep one session PER loop (keyed by
# id(loop)) — exactly like the per-loop asyncpg pools. A single shared session would
# break the 2nd concurrent interview ("Event loop is closed").
_aiohttp_sessions: dict = {}


async def _get_aiohttp_session():
    import aiohttp
    key = id(asyncio.get_running_loop())
    s = _aiohttp_sessions.get(key)
    if s is None or s.closed:
        s = aiohttp.ClientSession()
        _aiohttp_sessions[key] = s
    return s


async def _close_aiohttp_session() -> None:
    """Close + drop the current loop's aiohttp session (called in bot teardown)."""
    s = _aiohttp_sessions.pop(id(asyncio.get_running_loop()), None)
    if s is not None and not s.closed:
        await s.close()

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
# Seconds after the candidate's signaling connects to greet anyway if they never
# publish a mic (denied permission). The normal path greets on mic subscription.
GREETING_FALLBACK_SECONDS = float(os.getenv("GREETING_FALLBACK_SECONDS", "5"))
_interviews: dict = {}                      # room_name -> InterviewBot
_interviews_lock = asyncio.Lock()
# Only ONE bot may be in its LiveKit connect/handshake phase at a time. Each bot runs
# in its own thread, but concurrent room.connect()s contend for the GIL and can starve
# one bot's FFI ReadyForRoom handshake → panic. Serializing the connect window (a few
# seconds each) keeps concurrent interviews reliable; it's a threading.Lock because the
# bots are on different event loops/threads.
_CONNECT_SERIALIZE = threading.Lock()
_shutting_down = False
# The uvicorn/FastAPI event loop, captured at startup. Interview bots run on their
# OWN loop in a dedicated thread; they schedule the few main-loop operations (e.g.
# pruning _interviews) back onto this loop via call_soon_threadsafe.
_MAIN_LOOP: "asyncio.AbstractEventLoop | None" = None


class InterviewBot:
    """A single live interview: its own room, bot manager, and worker task."""
    def __init__(self, room_name: str, candidate_id: int, job_id: int):
        self.room_name = room_name
        self.candidate_id = candidate_id
        self.job_id = job_id
        self.manager = None
        self.session_id = None
        self.error = None
        # The bot runs on its OWN event loop in a dedicated thread (so the LiveKit FFI
        # room handshake isn't starved by the busy uvicorn loop). Hence thread-safe
        # primitives: a threading.Event for readiness (set from the bot loop, awaited
        # from the uvicorn loop via to_thread) and a Thread handle instead of a Task.
        self.ready = threading.Event()
        self.thread: "threading.Thread | None" = None
        self.loop: "asyncio.AbstractEventLoop | None" = None
        # Set when the candidate leaves and the worker is being torn down. A draining
        # bot must NOT be handed back to a re-opened link — the candidate would join a
        # dying room and see no resume. ensure_interview waits for it to finish, then
        # respawns a fresh bot that resumes the SAME session from the DB.
        self.draining = False
        # True while a candidate WebRTC participant is connected to this room. Written
        # from the bot thread (CPython GIL makes single-bool writes atomic), read from
        # the uvicorn thread in /interview/validate to reject a second concurrent join.
        self.candidate_connected: bool = False

    def alive(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

# --- FastAPI App ---
from contextlib import asynccontextmanager


def validate_required_keys() -> None:
    """Fail fast if the API keys the interview pipeline needs are missing/empty.

    ``os.environ["X"]`` only catches a *missing* var — an empty value (``X=``)
    sailed through and the service died mid-interview with a cryptic error. Here we
    check presence AND non-emptiness at startup so misconfiguration is loud and
    immediate. CARTESIA is only required when it's the selected TTS provider.
    """
    required = {
        "DEEPGRAM_API_KEY": "speech-to-text (and default TTS)",
        "GROQ_API_KEY": "responder + judge LLM",
    }
    if os.getenv("TTS_PROVIDER", "deepgram").lower() == "cartesia":
        required["CARTESIA_API_KEY"] = "text-to-speech (TTS_PROVIDER=cartesia)"

    missing = [name for name in required if not (os.getenv(name) or "").strip()]
    if missing:
        details = ", ".join(f"{n} ({required[n]})" for n in missing)
        raise RuntimeError(
            f"Missing/empty required API key(s): {details}. "
            "Set them in the environment (.env) before starting the interview server."
        )

    # The interview-link secret is the ONLY auth boundary for candidates — a missing
    # or placeholder value lets anyone forge an invite. Fail-closed, and it MUST match
    # the backend's value or minted links won't validate.
    ils = (os.getenv("INTERVIEW_LINK_SECRET") or "").strip()
    if not ils or "change-me" in ils:
        raise RuntimeError(
            "INTERVIEW_LINK_SECRET is not configured (or is a placeholder). Set a "
            "real 32+ byte random value that MATCHES the backend's INTERVIEW_LINK_SECRET."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """ASGI startup/shutdown.

    Starts a supervised DEFAULT bot (for the :7860 testing dashboard) that respawns
    if it idles out. REAL interviews are started on demand per room by
    ``ensure_interview`` (called from /interview/validate). Started here so any
    launcher (uvicorn runner:app, gunicorn, container CMD) boots the full system.
    """
    global _bot_task, _shutting_down, _MAIN_LOOP
    validate_required_keys()  # fail fast on misconfiguration, not mid-interview
    _shutting_down = False
    _MAIN_LOOP = asyncio.get_running_loop()
    if START_DEFAULT_BOT:
        _bot_task = asyncio.create_task(_supervise_default_bot())
    try:
        yield
    finally:
        _shutting_down = True
        if _bot_task and not _bot_task.done():
            _bot_task.cancel()
            try:
                await _bot_task
            except asyncio.CancelledError:
                pass
        # Interview bots run as daemon threads (each on its own loop); ask each to
        # stop, then let the process exit reap them. We don't hard-join — a stuck
        # LiveKit teardown must not block server shutdown.
        for b in list(_interviews.values()):
            if b.alive() and b.loop and b.manager:
                try:
                    b.loop.call_soon_threadsafe(
                        lambda b=b: asyncio.ensure_future(b.manager.worker.cancel())
                    )
                except Exception:
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
# operator endpoints are OPEN by default — no auth needed for local testing. The
# real security boundary for applicants is the SIGNED INTERVIEW LINK verified by
# /interview/validate.
#
# For an exposed/production deployment, set VOICE_REQUIRE_AUTH=true to require the
# shared admin bearer token on these operator endpoints.
# Genuine operator/system endpoints — gated when VOICE_REQUIRE_AUTH is on.
# /interview/validate and /events are candidate-open (they do their own token checks).
_PROTECTED_VOICE_ROUTES = {
    ("POST", "/interview/configure"),
    ("POST", "/chat"),
    ("POST", "/settings"),
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
    # Surface the configured providers + whether TTS has degraded (e.g. ran out of
    # credits) so a silently-broken provider is visible to operators, not hidden.
    tts_obj = getattr(bot_manager, "tts", None) if bot_manager else None
    tts_degraded = getattr(tts_obj, "degraded_reason", None) if tts_obj else None
    return {
        "status": status,
        "default_bot_running": default_running,
        "active_interviews": len(_interviews),
        "max_concurrent_interviews": MAX_CONCURRENT_INTERVIEWS,
        "error": err,
        "default_room": DEFAULT_ROOM,
        "session": bot_manager.session.session_id if (bot_manager and bot_manager.session) else "none",
        "services": {"STT": svc, "LLM": svc, "TTS": svc},
        "providers": {
            "stt": "groq-whisper" if os.getenv("BILINGUAL_MODE", "").lower() in ("1", "true", "yes") else "deepgram",
            "llm": f"groq:{os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')}",
            "tts": os.getenv("TTS_PROVIDER", "deepgram").lower(),
            "tts_degraded": tts_degraded,
        },
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

    # Defensive sanitize: a base64url JWT is strictly [A-Za-z0-9_-] plus two dots and
    # can never contain whitespace or '%'. Long links copied on a phone pick up
    # line-wrap whitespace, which arrives URL-encoded ('%20', or double-encoded
    # '%2520' through the same-origin proxy). Strip those spurious bytes so the token
    # verifies instead of failing signature check on copy/wrap corruption.
    token = re.sub(r"%(?:25)*20", "", token)  # encoded spaces (any encode depth)
    token = re.sub(r"\s+", "", token)          # literal whitespace

    try:
        claims = verify_invite_token(token, secret)
    except InviteTokenError as e:
        return {"valid": False, "error": f"This interview link is invalid or has expired ({e})."}

    # Deterministic session id per interview link (candidate + token jti). Re-opening
    # the same link maps to the SAME session row, so an interrupted interview resumes
    # in place rather than spawning a new session and overwriting the old recording.
    session_id = f"{claims.candidate_id}-{claims.jti}"

    # Single-use after completion: once an interview is finished, the link is spent —
    # this is the best-practice rule that also prevents re-running the bot and
    # overwriting the finished transcript/recording/evaluation.
    try:
        await db_manager._ensure_pool()
        prior_status = await db_manager.get_session_status(session_id)
    except Exception as e:
        logger.error(f"[Interview] status lookup failed: {e}")
        prior_status = None
    if prior_status == "completed":
        return {
            "valid": False,
            "error": "You have already completed this interview. This link can no longer be used.",
        }

    # Unique room per interview link (jti makes it unique). Spin up a dedicated bot
    # bound to THIS candidate/job — no shared room, no global state, no cross-talk.
    room = f"interview-{claims.candidate_id}-{claims.jti[:12]}"
    bot = await ensure_interview(claims.candidate_id, claims.job_id, room, session_id=session_id)
    if bot is None:
        return {
            "valid": False,
            "error": "All interview slots are currently busy. Please try again in a few minutes.",
        }
    if bot.error:
        return {"valid": False, "error": "Could not start the interview. Please contact the recruiter."}

    if bot.candidate_connected:
        return {
            "valid": False,
            "error": "This interview is already open in another browser or tab. "
                     "Please close that window and try again.",
        }

    try:
        await db_manager._ensure_pool()
        job = await db_manager.get_job(claims.job_id)
        candidate = await db_manager.get_candidate(claims.candidate_id)
    except Exception as e:
        logger.error(f"[Interview] validate lookup failed: {e}")
        job, candidate = None, None

    # On a resume, hand back the conversation so far so the candidate's page can
    # redisplay it immediately (the live SSE stream only carries NEW turns, never a
    # replay). Empty for a first-time join.
    prior_transcript: list = []
    if prior_status in ("active", "interrupted"):
        try:
            prior_transcript = await db_manager.get_transcript(session_id)
        except Exception as e:
            logger.error(f"[Interview] prior transcript lookup failed: {e}")

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
        # Use the canonical {candidate_id}-{jti} session_id (the value the bot persists
        # under) rather than bot.session_id, which is still None at validate time before
        # the bot configures — a null here breaks the client's live-transcript scoping.
        "session_id": session_id,  # lets the client filter the live event stream
        "livekit_token": lk_token,
        "livekit_url": os.getenv("LIVEKIT_URL"),
        "prior_transcript": prior_transcript,  # conversation so far, for resume redisplay
        # Soft guideline duration for the candidate's on-screen countdown (the interview
        # actually ends on completion/idle, not a hard time cap).
        "time_limit_seconds": int(os.getenv("INTERVIEW_TIME_LIMIT_SECS", "1800")),
    }

@app.get("/interview/debug/{session_id}")
async def interview_debug(session_id: str):
    """Read-only resume diagnostics for one session — verify state without psql.

    Returns the persisted status, whether the link would be treated as a resume,
    the question-flow position, and a transcript turn count + tail. No secrets; safe
    to hit from a browser while manually testing resume-on-restart."""
    from database import db_manager
    try:
        await db_manager._ensure_pool()
        status = await db_manager.get_session_status(session_id)
        progress = await db_manager.get_session_progress(session_id)
        transcript = await db_manager.get_transcript(session_id)
    except Exception as e:
        logger.error(f"[Interview] debug lookup failed for {session_id}: {e}")
        return {"session_id": session_id, "error": str(e)}

    # Mirror the resume rule in bot_manager.configure_session.
    resumable = status in ("active", "interrupted")
    states = (progress or {}).get("question_states", {})
    return {
        "session_id": session_id,
        "exists": status is not None,
        "status": status,
        "resumable": resumable,
        "single_use_spent": status == "completed",
        "current_question_index": (progress or {}).get("current_question_index", 0),
        "question_states": states,
        "questions_covered": sum(
            1 for s in states.values()
            if isinstance(s, dict) and s.get("status") in ("covered", "weak", "skipped")
        ),
        "transcript_turns": len(transcript),
        "transcript_tail": [
            {"speaker": t["speaker"], "text": (t["text"] or "")[:120]}
            for t in transcript[-4:]
        ],
        "live": bool(bot_manager and bot_manager.session
                     and bot_manager.session.session_id == session_id),
    }


@app.get("/events")
async def sse_events(session: str | None = None):
    # `session` scopes the stream to one interview (candidate page passes its
    # session_id); omitted = unfiltered (dashboard sees all).
    queue = await broadcaster.subscribe(session)
    logger.debug("Client subscribed to events stream")
    async def event_generator():
        # SSE comment sent immediately so the Next.js proxy's ReadableStream.pull()
        # receives a first chunk right away — without this the proxy route handler
        # holds open its fetch() without ever flushing response headers to the browser
        # (Next.js 15 standalone calls pull() before sending the 200 status line).
        yield ": connected\n\n"
        try:
            while True:
                message = await queue.get()
                yield message
        except asyncio.CancelledError:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

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
        # Snapshot: _interviews is mutated from bot threads, so iterate a copy.
        for b in list(_interviews.values()):
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


@app.post("/interview/end")
async def end_interview(request: Request):
    """End an interview NOW so it finalizes immediately — saving the recording and
    running the post-call evaluation — instead of waiting for the idle timeout. Used
    by the mock driver when it finishes; cancelling the worker triggers
    finalize_session in _make_and_run_bot's finally block."""
    data = await request.json()
    session = data.get("session")
    if not session:
        return {"error": "no session provided"}
    for b in list(_interviews.values()):  # snapshot — mutated from bot threads
        if b.session_id == session and b.manager:
            try:
                await b.manager.worker.cancel()
            except Exception as e:  # noqa: BLE001
                return {"error": f"could not end: {e}"}
            return {"status": "ending"}
    return {"error": "interview not found or already ended"}

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
    return {"mode": "dual", "status": "not_started"}

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


def _qt_list(v):
    """question_templates comes back from JSONB as a list or a JSON string."""
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, list) else []
        except (TypeError, ValueError):
            return []
    return []


@app.get("/jobs/{job_id}/questions")
async def get_job_questions(job_id: int):
    """The interview question bank for a job, resolved to its role. Questions are stored
    per ROLE (goal_templates.role_type), so jobs sharing a role share this bank."""
    from database import db_manager
    from recruiter_shared import normalize_role_type
    job = await db_manager.get_job(job_id)
    if not job:
        return {"error": "job not found"}
    role_slug = normalize_role_type(job.get("role_type") or job.get("title") or "")
    templates = await db_manager.get_goal_templates(role_slug)
    return {
        "job_id": job_id,
        "role_type": role_slug,
        "goals": [
            {
                "id": str(t["id"]),
                "title": t.get("title") or "",
                "description": t.get("description") or "",
                "priority_weight": float(t.get("priority_weight") or 0.5),
                "questions": _qt_list(t.get("question_templates")),
            }
            for t in templates
        ],
    }


@app.put("/goals/templates/{template_id}")
async def update_goal_template_api(template_id: str, request: Request):
    """Edit one goal's title/description/questions in place (FK-safe)."""
    from database import db_manager
    data = await request.json()
    try:
        await db_manager.update_goal_template(
            template_id,
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            question_templates=[str(q) for q in (data.get("questions") or []) if str(q).strip()],
            priority_weight=float(data.get("priority_weight", 0.5)),
        )
        return {"status": "updated", "id": template_id}
    except Exception as e:
        logger.error(f"[API] Failed to update goal template {template_id}: {e}")
        return {"error": str(e)}


async def _persist_agent_line(manager, session_id, text):
    """Persist a directly-spoken agent line (greeting) to the transcript.

    The greeting is pushed as a raw TTS frame and never passes through the
    LLM-response aggregator that persists normal agent turns, so we record it here.
    Best-effort: never let a transcript write block the greeting."""
    if not session_id or not (manager and manager.session):
        return
    try:
        import time
        from database import db_manager
        await db_manager.add_transcript_entry(session_id, {
            "speaker": "agent",
            "text": text,
            "timestamp": str(time.time()),
            "tokens_estimated": len(text.split()),
        })
    except Exception as e:
        logger.debug(f"[Bot] greeting transcript persist skipped: {e}")


# --- Bot runner (one bot per room) ---
async def _make_and_run_bot(room_name, candidate_id, job_id, *, is_default, bot_ref=None, session_id=None):
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
    _noise_cancel = os.getenv("NOISE_CANCELLATION", "true").lower() not in ("0", "false", "no")
    transport = LiveKitTransport(
        url=url, token=token, room_name=room_name,
        params=LiveKitParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            # Server-side RNNoise filter on the inbound audio stream.  Runs fully
            # in-process (no API key) and reduces background noise before STT sees it,
            # lowering false transcriptions and spurious interruptions.
            audio_in_filter=RNNoiseFilter() if _noise_cancel else None,
            # Ingest the candidate's camera so BotManager can record video.
            video_in_enabled=RECORD_VIDEO,
        ),
    )
    # LiveKit's Python FFI needs an UNBLOCKED event loop to finish its room handshake
    # (the ReadyForRoomEventRequest step). When STT/LLM startup fires on the same
    # StartFrame, their network connects starve that handshake → "timed out ... after
    # ConnectCallback" panic, which is WORSE in slower containers (livekit/agents#4183:
    # LiveKit considers a blocked loop the caller's responsibility). So we GATE the heavy
    # services' start() on the room actually being connected: the transport connects on a
    # quiet loop first, then STT/LLM proceed. No audio flows until the candidate joins, so
    # deferring STT/LLM start by the ~couple seconds of connect time is harmless.
    connected_evt = asyncio.Event()

    # Global connect-serialization (see _CONNECT_SERIALIZE): held only during THIS bot's
    # connect window, released the instant it's in the room (or by a failsafe timer).
    _connect_lock_state = {"held": False}

    def _release_connect_lock():
        if _connect_lock_state["held"]:
            _connect_lock_state["held"] = False
            try:
                _CONNECT_SERIALIZE.release()
            except Exception:
                pass

    def _gate_on_connect(service):
        """Defer a pipecat service's start() until the LiveKit room is connected."""
        _orig_start = service.start
        svc_name = service.__class__.__name__

        async def _gated_start(frame):
            if not connected_evt.is_set():
                try:
                    logger.debug(f"[Gate] {svc_name}.start() waiting for LiveKit connect")
                    await asyncio.wait_for(connected_evt.wait(), timeout=30.0)
                except asyncio.TimeoutError:
                    logger.warning(f"[Gate] {svc_name}.start() timed out waiting for connect")
                    pass  # connect failed/slow — proceed so the pipeline never hangs
            logger.debug(f"[Gate] {svc_name}.start() calling original start")
            await _orig_start(frame)
            logger.debug(f"[Gate] {svc_name}.start() done")

        service.start = _gated_start

    _bilingual = os.getenv("BILINGUAL_MODE", "").lower() in ("1", "true", "yes")
    if _bilingual:
        # Bilingual English + Roman Urdu mode: use Groq Whisper (supports Urdu auto-detect).
        # language=None → auto-detect per utterance (handles English / Roman Urdu mix).
        # prompt guides Whisper to keep Roman Urdu in Latin script rather than transliterating.
        stt = GroqSTTService(
            api_key=os.environ["GROQ_API_KEY"],
            settings=GroqSTTService.Settings(
                model="whisper-large-v3-turbo",
                language=None,  # auto-detect English / Urdu per utterance
                prompt=(
                    "The speaker may use Roman Urdu (Urdu in Latin script) mixed with English. "
                    "Transcribe Urdu words phonetically in Roman Urdu (Latin script), "
                    "not in Arabic/Nastaliq script. Example: 'mera tajurba teen saal ka hai'."
                ),
            ),
        )
        logger.info("[STT] Bilingual mode: GroqSTTService (Whisper) with Roman Urdu auto-detect")
    else:
        stt_kwargs = {"api_key": os.environ["DEEPGRAM_API_KEY"]}
        # filler_words=true makes Deepgram transcribe hesitation fillers ("um", "uh",
        # "hmm", etc.) instead of dropping them — useful signal for delivery/assessment.
        stt_settings = {"extra": {"filler_words": True}}
        if DEEPGRAM_ENDPOINTING_MS is not None:
            stt_settings["endpointing"] = DEEPGRAM_ENDPOINTING_MS
        stt_kwargs["settings"] = DeepgramSTTService.Settings(**stt_settings)
        stt = DeepgramSTTService(**stt_kwargs)
        logger.info("[STT] Deepgram streaming STT")
    llm = GroqLLMService(
        api_key=os.environ["GROQ_API_KEY"],
        settings=GroqLLMService.Settings(model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")),
    )
    # Hold STT (Deepgram WS) + LLM startup until the LiveKit room is connected, so their
    # network handshakes don't starve the FFI room handshake (see _gate_on_connect above).
    _gate_on_connect(stt)
    _gate_on_connect(llm)
    # TTS provider. Default to Deepgram Aura over HTTP: a persistent websocket (the old
    # default) dropped under load and looped on "reconnecting", so speech failed often.
    # The HTTP service does one request per utterance — no socket to drop — which is the
    # reliable default here. TTS_PROVIDER overrides: 'deepgram' (websocket), 'cartesia'.
    tts_provider = os.getenv("TTS_PROVIDER", "deepgram_http").lower()
    deepgram_voice = os.getenv("DEEPGRAM_VOICE", "aura-2-thalia-en")
    if tts_provider == "cartesia":
        tts = ResilientCartesiaTTSService(
            api_key=os.environ["CARTESIA_API_KEY"],
            settings=ResilientCartesiaTTSService.Settings(
                voice=os.getenv("CARTESIA_VOICE_ID", "71a7ad14-091c-4e8e-a314-022ece01c121")),
        )
    elif tts_provider == "deepgram":  # persistent websocket (legacy)
        tts = ResilientDeepgramTTSService(
            api_key=os.environ["DEEPGRAM_API_KEY"], voice=deepgram_voice,
        )
    else:  # deepgram_http (default) — robust request/response TTS
        tts = ResilientDeepgramHttpTTSService(
            api_key=os.environ["DEEPGRAM_API_KEY"], voice=deepgram_voice,
            aiohttp_session=await _get_aiohttp_session(),
        )
    logger.info(f"[TTS] provider={tts_provider}")
    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            user_turn_strategies=build_user_turn_strategies()),
    )
    manager = BotManager(transport, stt, llm, tts, context, user_aggregator, assistant_aggregator)

    # Patch DeepgramSTTService._connection_handler to add retry backoff.
    # Without backoff the tight WebSocket retry loop (on e.g. an invalid API key) can
    # starve the event loop and prevent StartFrame from propagating through the pipeline,
    # leaving PipelineWorker stuck in _wait_for_pipeline_start indefinitely.
    import types as _types, asyncio as _asyncio_stt
    async def _patched_connection_handler(self):
        while True:
            connect_kwargs = self._build_connect_kwargs()
            keepalive_task = None
            try:
                async with self._client.listen.v1.connect(**connect_kwargs) as connection:
                    self._connection = connection
                    self._connection_ready.set()
                    from deepgram.core.events import EventType as _EvtType
                    connection.on(_EvtType.MESSAGE, self._on_message)
                    connection.on(_EvtType.ERROR, self._on_error)
                    logger.debug(f"{self}: Websocket connection initialized")
                    keepalive_task = self.create_task(
                        self._keepalive_handler(), f"{self}::keepalive"
                    )
                    await connection.start_listening()
            except Exception as e:
                logger.warning(f"{self}: Connection lost, will retry: {e}")
                await _asyncio_stt.sleep(2.0)
            finally:
                self._connection_ready.clear()
                self._connection = None
                if keepalive_task:
                    await self.cancel_task(keepalive_task)
    # Only patch DeepgramSTTService — GroqSTTService (bilingual mode) uses a different transport.
    if isinstance(stt, DeepgramSTTService):
        stt._connection_handler = _types.MethodType(_patched_connection_handler, stt)

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
            pre_session = await create_session_for(candidate_id, job_id, session_id=session_id)
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
        sid = manager.session.session_id if manager.session else None
        resumed = getattr(manager, "resumed", False)

        if resumed:
            # The candidate re-opened the same link mid-interview. configure_session has
            # already replayed the prior conversation into the LLM context AND injected a
            # system instruction listing covered topics + the next question, so don't
            # re-run the intro — say a short "welcome back" and let the LLM continue.
            greeting = "Welcome back. Let's pick up right where we left off."
            await broadcaster.broadcast("transcript", {"session_id": sid, "speaker": "agent", "text": greeting})
            try:
                context.add_message({"role": "assistant", "content": greeting})
            except Exception:
                pass
            await _persist_agent_line(manager, sid, greeting)
            from pipecat.frames.frames import TTSSpeakFrame, LLMRunFrame
            # Inject at the pipeline SOURCE (transport input) so the frame flows DOWN
            # the chain to the TTS — same path inject_text() uses. Pushing on
            # manager.pipeline pushes OUT of the pipeline, so the TTS never sees it
            # and the bot stays silent.
            await manager.transport.input().push_frame(TTSSpeakFrame(greeting))
            # Let the LLM produce the next question from the restored history + summary.
            await manager.transport.input().push_frame(LLMRunFrame())
            return

        greeting = (
            f"Hello, and welcome to your interview for {role}. " if role
            else "Hello, and welcome to your interview. "
        ) + (
            "I'm your AI interviewer. To get started, could you tell me a little "
            "about yourself and your background?"
        )
        await broadcaster.broadcast("transcript", {"session_id": sid, "speaker": "agent", "text": greeting})
        try:
            context.add_message({"role": "assistant", "content": greeting})
        except Exception:
            pass
        # Persist the opening line. The greeting is pushed straight to TTS (it never goes
        # through the LLM-response aggregation that normally persists agent turns), so
        # without this an early reload would find an empty transcript and replay the intro.
        await _persist_agent_line(manager, sid, greeting)
        from pipecat.frames.frames import TTSSpeakFrame
        # Inject at the pipeline SOURCE (transport input) so it reaches the TTS —
        # manager.pipeline.push_frame pushes OUT of the pipeline, leaving the bot silent.
        await manager.transport.input().push_frame(TTSSpeakFrame(greeting))

    @transport.event_handler("on_connected")
    async def on_connected(transport, *args):
        # Bot is now actually IN the room. Bind the session here (before the
        # candidate joins) so even an early message has the right session_id, and
        # only NOW mark ready — so validate waits until the bot is in the room and
        # the candidate never joins an empty room.
        logger.info(f"[Bot] Connected to room {room_name}")
        connected_evt.set()  # release the gated STT/LLM start now the FFI handshake is done
        _release_connect_lock()  # let the next queued bot start its connect
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
        if str(identity) != "recruiter-bot" and bot_ref:
            bot_ref.candidate_connected = True
        # Do NOT greet here. participant_connected fires the instant the candidate's
        # SIGNALING connects — before their browser has subscribed to our audio track
        # and started playback. Greeting now races ahead of their audio and the first
        # message is never heard. We greet from on_audio_track_subscribed instead (media
        # negotiated both ways = candidate can hear us). Fallback-greet only if the
        # candidate never publishes a mic (e.g. denied permission), so they still start.
        async def _fallback_greet(idn):
            try:
                await asyncio.sleep(GREETING_FALLBACK_SECONDS)
                if not _greeted["done"]:
                    logger.info(f"[Bot] Fallback greeting (no mic subscription) in {room_name}")
                    await _greet_once(idn)
            except asyncio.CancelledError:
                pass
        if not _greeted["done"]:
            asyncio.create_task(_fallback_greet(identity))

    @transport.event_handler("on_audio_track_subscribed")
    async def on_audio_track_subscribed(transport, participant, *rest):
        # Primary greeting trigger: fires when the bot subscribes to the candidate's
        # mic, which means media is negotiated both ways — so the candidate has also
        # subscribed to our audio track and (with the client's startAudio) can hear the
        # greeting. This is the reliable "candidate is ready" signal.
        identity = getattr(participant, "identity", participant)
        await _greet_once(identity)

    @transport.event_handler("on_participant_disconnected")
    async def on_participant_disconnected(transport, participant):
        identity = getattr(participant, "identity", participant)
        logger.info(f"UI Left Room {room_name}: {identity}")
        await broadcaster.broadcast("participant", {"event": "dropped", "identity": str(identity)})
        # End a REAL interview when the candidate leaves — frees the slot/room.
        if not is_default and str(identity) != "recruiter-bot":
            if bot_ref:
                bot_ref.candidate_connected = False
            # Mark draining FIRST so a fast re-open doesn't grab this dying bot.
            if bot_ref:
                bot_ref.draining = True
            try:
                await manager.worker.cancel()
            except Exception:
                pass

    await manager.start()
    runner = WorkerRunner(handle_sigint=False)  # only the process owner handles signals
    await runner.add_workers(manager.worker)

    # Take the global connect slot so only this bot handshakes at a time. Acquired
    # off-loop (to_thread) so waiting doesn't block this bot's loop; released in
    # on_connected, plus a failsafe timer in case connect never completes.
    await asyncio.to_thread(_CONNECT_SERIALIZE.acquire)
    _connect_lock_state["held"] = True
    asyncio.get_running_loop().call_later(25.0, _release_connect_lock)
    logger.info(f"🚀 Bot joining room {room_name} (candidate={candidate_id}, job={job_id})")
    # readiness is signalled from the on_connected handler (above), i.e. once the
    # bot is actually in the room — not here, where it has only started connecting.
    try:
        await runner.run()
    finally:
        _release_connect_lock()  # belt-and-suspenders: never hold the slot past the run
        # The worker has ended (disconnect / idle / cancel). Run the final goal
        # analysis and persist the assessment exactly once, for REAL interviews
        # only — the always-on default bot has no candidate/session to finalize.
        if not is_default:
            # Graceful = the interview reached its natural end (all questions covered);
            # it drives the goal/score wrap-up. terminal=True ALWAYS spends the link:
            # once the worker ends (a party left the call, idle timeout, or cancel) the
            # interview is over and the link must NOT resume the session. Recording /
            # transcript / analysis are still saved for HR.
            graceful = bool(manager.session and manager.session.is_complete)
            try:
                await manager.finalize_session(graceful=graceful, terminal=True)
            except Exception as e:
                logger.error(f"[Bot] finalize_session failed for {room_name}: {e}")


async def ensure_interview(candidate_id, job_id, room_name, session_id=None):
    """Get-or-spawn the dedicated bot for an interview room. Returns the
    InterviewBot, or None if the concurrency cap is reached.

    ``session_id`` (deterministic per interview link) is threaded to the bot so a
    respawn after an interruption resumes the SAME session row/recording/transcript."""
    # If a prior bot for this room is still tearing down (candidate just dropped),
    # wait for it to finish OUTSIDE the lock before deciding — otherwise a fast
    # re-open would be handed the dying bot and join an empty/closing room. The fresh
    # bot we spawn below resumes the SAME session from the DB.
    draining = _interviews.get(room_name)
    if draining and draining.draining and draining.alive():
        logger.info(f"[Interview] {room_name} is draining; waiting before respawn")
        try:
            await asyncio.to_thread(draining.thread.join, 15.0)
        except Exception:
            pass

    async with _interviews_lock:
        existing = _interviews.get(room_name)
        if existing and not existing.draining and existing.alive():
            return existing
        # prune finished
        for rn in [rn for rn, b in _interviews.items() if not b.alive()]:
            _interviews.pop(rn, None)
        if len(_interviews) >= MAX_CONCURRENT_INTERVIEWS:
            logger.warning(f"[Interview] capacity reached ({MAX_CONCURRENT_INTERVIEWS}); refusing {room_name}")
            return None

        bot = InterviewBot(room_name, candidate_id, job_id)

        def _drop_self():
            # Runs on the MAIN loop (scheduled via call_soon_threadsafe). Only remove
            # ourselves — a re-opened link may have already replaced us with a fresh
            # resuming bot under the same room name.
            if _interviews.get(room_name) is bot:
                _interviews.pop(room_name, None)
            logger.info(f"[Interview {room_name}] ended; slot freed ({len(_interviews)} active)")

        def _thread_main():
            # The bot gets its OWN event loop, isolated from the uvicorn loop, so the
            # blocking LiveKit FFI room handshake (and STT/LLM startup) can't starve
            # the FFI event pump — the root cause of the ReadyForRoomEventRequest panic.
            from database import db_manager
            loop = asyncio.new_event_loop()
            bot.loop = loop
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    _make_and_run_bot(room_name, candidate_id, job_id, is_default=False,
                                      bot_ref=bot, session_id=session_id)
                )
            except Exception as e:
                logger.error(f"[Interview {room_name}] worker error: {e}")
                bot.error = str(e)
                bot.ready.set()
            finally:
                # Close THIS loop's per-loop resources (asyncpg pool + aiohttp TTS
                # session), then tear the loop down.
                try:
                    loop.run_until_complete(db_manager.close())
                except Exception:
                    pass
                try:
                    loop.run_until_complete(_close_aiohttp_session())
                except Exception:
                    pass
                try:
                    loop.close()
                except Exception:
                    pass
                if _MAIN_LOOP and not _MAIN_LOOP.is_closed():
                    _MAIN_LOOP.call_soon_threadsafe(_drop_self)

        t = threading.Thread(target=_thread_main, name=f"bot-{room_name}", daemon=True)
        bot.thread = t
        _interviews[room_name] = bot
        t.start()

    # Wait until the bot is actually IN the room (on_connected sets ready), so the
    # candidate joins to a present, configured bot — not an empty room. LiveKit
    # cold-connect can occasionally take ~20s, hence the generous timeout. The bot
    # runs in another thread, so wait on its threading.Event off the uvicorn loop.
    try:
        await asyncio.to_thread(bot.ready.wait, 35.0)
    except Exception:
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
