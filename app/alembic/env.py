"""Alembic environment for the FastAPI backend.

Connection is built from DATABASE_URL (same source as app/database.py).
For SQLite compatibility all table alterations use batch mode.

Existing databases (no alembic_version table, but tables already present)
are stamped to 'head' automatically so the first `upgrade head` is a no-op.
"""

import os
import logging
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from alembic import context

load_dotenv()

alembic_cfg = context.config

if alembic_cfg.config_file_name is not None:
    fileConfig(alembic_cfg.config_file_name)

logger = logging.getLogger("alembic.env")


def _database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        os.getenv("ALEMBIC_DATABASE_URL", "sqlite:///ai_recruiter.db"),
    )


# No autogenerate — migrations are written by hand so they work on both
# SQLite and PostgreSQL without surprises.
target_metadata = None


def _stamp_existing_if_needed(connection) -> None:
    """If the DB has application tables but no alembic_version, stamp to head.

    This marks all migrations as already applied without running them, which is
    correct for databases created before Alembic was introduced.
    """
    inspector = inspect(connection)
    tables = inspector.get_table_names()
    if "jobs" in tables and "alembic_version" not in tables:
        logger.info(
            "Existing database detected (no alembic_version). "
            "Stamping to head without running migrations."
        )
        connection.execute(
            text(
                "CREATE TABLE alembic_version "
                "(version_num VARCHAR(32) NOT NULL, "
                "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
            )
        )
        # Insert the latest revision id so `alembic upgrade head` is a no-op.
        # This value must match the `revision` field in the latest version file.
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('0001_initial')")
        )
        connection.commit()


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _database_url()
    connectable = create_engine(
        url,
        connect_args={"check_same_thread": False} if "sqlite" in url else {},
    )
    with connectable.connect() as connection:
        _stamp_existing_if_needed(connection)
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
