import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.logging_config import setup_logging
from .core.auth import admin_token_guard
from .database import engine, Base, config, run_migrations, DATABASE_URL
from .llm.groq_client import get_groq_client
from .queue.worker import start_worker, stop_worker, requeue_pending
from .events.broadcaster import event_hub
from .routers import admin, jobs, iq, candidates, interviews, availability

load_dotenv()
setup_logging(config.get("logging", {}).get("level", "INFO"))


def _run_alembic_upgrade() -> None:
    """Run `alembic upgrade head` programmatically.

    env.py auto-stamps existing databases (no alembic_version table, but application
    tables already present) so this is a no-op for pre-Alembic installations.
    Falls back to legacy run_migrations() if alembic is unavailable.
    """
    try:
        import pathlib
        from alembic.config import Config as AlembicConfig
        from alembic import command as alembic_command

        ini = pathlib.Path(__file__).parent.parent / "alembic.ini"
        cfg = AlembicConfig(str(ini))
        alembic_command.upgrade(cfg, "head")
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).warning(
            "Alembic upgrade failed (%s); falling back to run_migrations()", exc
        )
        run_migrations()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    event_hub.bind_loop(asyncio.get_running_loop())
    Base.metadata.create_all(bind=engine)
    _run_alembic_upgrade()
    start_worker()
    requeue_pending()  # recover candidates a prior crash left in Queued/Processing
    get_groq_client()
    # Load heavy sentence‑transformer embedding model once at startup to avoid first‑request latency
    from .core.model_registry import get_embedding_model
    get_embedding_model()
    yield
    # Shutdown
    stop_worker()


app = FastAPI(title="AI Recruiter API", version="2.0.0", lifespan=lifespan)

# Require a valid admin bearer token on every non-public endpoint (logic in
# core/auth.py so it stays unit-testable).
app.middleware("http")(admin_token_guard)

# Added AFTER the auth guard so CORS stays the OUTERMOST middleware — this ensures
# even 401/503 responses carry CORS headers. Explicit allowlist instead of "*".
_cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(admin.router)
app.include_router(jobs.router)
app.include_router(iq.router)
app.include_router(candidates.router)
app.include_router(interviews.router)
app.include_router(availability.router)
