import os
import logging
import yaml
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load .env BEFORE resolving DATABASE_URL: this module reads the env at import
# time, and it is imported before main.py's own load_dotenv() runs. Without this
# the app silently falls back to SQLite even when DATABASE_URL is set in .env.
load_dotenv()
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


config = load_config()

# PostgreSQL migration: set DATABASE_URL env to override config.yaml
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    config.get("database", {}).get("url", "sqlite:///ai_recruiter.db"),
)

if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

connect_args = {}
engine_kwargs = {"pool_pre_ping": True}
if "sqlite" in DATABASE_URL:
    connect_args["check_same_thread"] = False
else:
    # Tune the connection pool for the API + background worker under concurrency.
    # SQLite uses its own (non-overflow) pool, so these apply only to real DBs.
    engine_kwargs.update(
        pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),  # recycle stale conns
        pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
    )

engine = create_engine(DATABASE_URL, connect_args=connect_args, **engine_kwargs)

if DATABASE_URL.startswith("sqlite"):
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    """Apply additive schema migrations (SQLite + PostgreSQL compatible)."""
    migrations = [
        "ALTER TABLE jobs ADD COLUMN role_type VARCHAR",
        "ALTER TABLE jobs ADD COLUMN tier1_weight FLOAT DEFAULT 1.0",
        "ALTER TABLE jobs ADD COLUMN tier2_weight FLOAT DEFAULT 1.0",
        "ALTER TABLE jobs ADD COLUMN tier3_weight FLOAT DEFAULT 1.0",
        "ALTER TABLE candidates ADD COLUMN job_id INTEGER",
        "ALTER TABLE candidates ADD COLUMN warnings TEXT",
        "ALTER TABLE candidates ADD COLUMN evaluation_data TEXT",
        # current_role is a reserved word in PostgreSQL — must be quoted.
        'ALTER TABLE candidates ADD COLUMN "current_role" VARCHAR',
        "ALTER TABLE candidates ADD COLUMN companies TEXT",
        "ALTER TABLE candidates ADD COLUMN skills_matched TEXT",
        "ALTER TABLE candidates ADD COLUMN skills_missing TEXT",
        "ALTER TABLE candidates ADD COLUMN hr_status VARCHAR",
        "ALTER TABLE candidates ADD COLUMN hr_notes TEXT",
        "ALTER TABLE candidates ADD COLUMN hr_score_override FLOAT",
        "ALTER TABLE candidates ADD COLUMN status_history TEXT",
        "ALTER TABLE candidates ADD COLUMN interview_invited_at VARCHAR",
        "ALTER TABLE candidates ADD COLUMN llm_prompt_tokens INTEGER",
        "ALTER TABLE candidates ADD COLUMN llm_completion_tokens INTEGER",
        "ALTER TABLE candidates ADD COLUMN llm_cost_usd FLOAT",
        "ALTER TABLE candidates ADD COLUMN years_experience FLOAT",
        "ALTER TABLE candidates ADD COLUMN interview_questions TEXT",
        "ALTER TABLE candidates ADD COLUMN iq_score FLOAT",
        "ALTER TABLE candidates ADD COLUMN iq_correct INTEGER",
        "ALTER TABLE candidates ADD COLUMN iq_total INTEGER",
        "ALTER TABLE candidates ADD COLUMN iq_time_seconds INTEGER",
        "ALTER TABLE candidates ADD COLUMN iq_attempted_at VARCHAR",
        "ALTER TABLE candidates ADD COLUMN iq_details TEXT",
    ]
    with engine.connect() as conn:
        for stmt in migrations:
            try:
                conn.execute(text(stmt))
                conn.commit()
                logger.info("Migration applied: %s", stmt)
            except Exception as e:
                conn.rollback()
                msg = str(e).lower()
                # "already applied" is the expected/idempotent case for additive
                # ALTERs; anything else is a REAL failure and must not be silent.
                if "already exists" in msg or "duplicate column" in msg:
                    logger.debug("Migration already applied: %s", stmt)
                else:
                    logger.warning("Migration failed (%s): %s", stmt, e)
