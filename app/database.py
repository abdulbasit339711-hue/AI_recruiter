import os
import logging
import yaml
from sqlalchemy import create_engine, text
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
if "sqlite" in DATABASE_URL:
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

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
        "ALTER TABLE candidates ADD COLUMN job_id INTEGER",
        "ALTER TABLE candidates ADD COLUMN warnings TEXT",
        "ALTER TABLE candidates ADD COLUMN evaluation_data TEXT",
        "ALTER TABLE candidates ADD COLUMN current_role VARCHAR",
        "ALTER TABLE candidates ADD COLUMN companies TEXT",
        "ALTER TABLE candidates ADD COLUMN skills_matched TEXT",
        "ALTER TABLE candidates ADD COLUMN skills_missing TEXT",
        "ALTER TABLE candidates ADD COLUMN hr_status VARCHAR",
        "ALTER TABLE candidates ADD COLUMN hr_notes TEXT",
        "ALTER TABLE candidates ADD COLUMN hr_score_override FLOAT",
        "ALTER TABLE candidates ADD COLUMN status_history TEXT",
    ]
    with engine.connect() as conn:
        for stmt in migrations:
            try:
                conn.execute(text(stmt))
                conn.commit()
                logger.info("Migration applied: %s", stmt)
            except Exception:
                conn.rollback()
