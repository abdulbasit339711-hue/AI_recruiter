"""Alembic environment.

The database connection is built from the same DB_* environment variables the
voice agent uses (see database.py / .env), so migrations always target the same
database as the application. No URL is stored in alembic.ini.
"""

import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

# Load .env so DB_* are available when running `alembic` from the shell.
load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _database_url() -> str:
    """Build a psycopg2 sync URL from DB_* env vars (override with DATABASE_URL)."""
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit

    user = os.getenv("DB_USER", "ai_user")
    password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "ai_recruiter")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


# These migrations use raw SQL (op.execute), so there is no SQLAlchemy metadata
# to autogenerate against.
target_metadata = None


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection (`alembic upgrade --sql`)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


_BOOTSTRAP_HINT = (
    "\n\n"
    "  The application role lacks the privileges these migrations need (this is\n"
    "  expected on a fresh database). Run the one-time bootstrap first:\n\n"
    "      uv run python scripts/bootstrap_db.py\n\n"
    "  It is idempotent and also applies migrations. See alembic/README.md.\n"
)


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    except Exception as exc:
        # A fresh DB where bootstrap.sql was never run fails here with
        # "permission denied for schema public" (or for a specific table).
        # Turn that into actionable guidance instead of a raw traceback.
        if "permission denied" in str(exc).lower():
            raise SystemExit(f"✗ Migration failed: {str(exc).strip()}{_BOOTSTRAP_HINT}") from exc
        raise


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
