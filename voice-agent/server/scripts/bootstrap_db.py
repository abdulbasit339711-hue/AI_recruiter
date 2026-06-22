#!/usr/bin/env python
"""Idempotent first-time database bootstrap for the voice agent.

This replaces the manual, easy-to-miss superuser step:

    sudo -u postgres psql -d ai_recruiter -f alembic/bootstrap.sql
    uv run alembic upgrade head

with a single command that is safe to re-run:

    uv run python scripts/bootstrap_db.py

What it does (each step is a no-op if already satisfied):

  1. Connect to PostgreSQL as a SUPERUSER (DB_SUPERUSER / DB_SUPERUSER_PASSWORD,
     default ``postgres``) against the maintenance database.
  2. Ensure the application role (DB_USER, default ``ai_user``) exists and its
     password matches DB_PASSWORD.
  3. Ensure the application database (DB_NAME) exists.
  4. Run ``alembic/bootstrap.sql`` as the superuser against DB_NAME — this grants
     the app role CREATE on the public schema and clears legacy postgres-owned
     goal-tracking objects so Alembic can recreate them owned by the app role.
  5. Unless ``--no-migrate`` is passed, run ``alembic upgrade head`` as the
     application role.

The superuser credentials are used ONLY here; the application and migrations
always connect as the unprivileged DB_USER. See alembic/README.md.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

SERVER_DIR = Path(__file__).resolve().parent.parent
BOOTSTRAP_SQL = SERVER_DIR / "alembic" / "bootstrap.sql"


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _superuser_dsn(dbname: str) -> dict:
    """Connection kwargs for the privileged bootstrap role."""
    return {
        "host": _env("DB_HOST", "localhost"),
        "port": int(_env("DB_PORT", "5432")),
        "user": _env("DB_SUPERUSER", "postgres"),
        "password": _env("DB_SUPERUSER_PASSWORD"),
        "dbname": dbname,
    }


def _connect_super(dbname: str):
    try:
        conn = psycopg2.connect(**_superuser_dsn(dbname))
    except psycopg2.OperationalError as exc:
        su = _env("DB_SUPERUSER", "postgres")
        sys.exit(
            f"\n✗ Could not connect as superuser '{su}' to '{dbname}' "
            f"at {_env('DB_HOST', 'localhost')}:{_env('DB_PORT', '5432')}.\n"
            f"  {str(exc).strip()}\n\n"
            f"  Set DB_SUPERUSER / DB_SUPERUSER_PASSWORD in .env (a role allowed to\n"
            f"  CREATE ROLE and CREATE DATABASE), or run the SQL manually as documented\n"
            f"  in alembic/README.md. On a default local install try:\n"
            f"      DB_SUPERUSER=postgres DB_SUPERUSER_PASSWORD=... uv run python scripts/bootstrap_db.py\n"
            f"  or, if your OS uses peer auth:\n"
            f"      sudo -u postgres psql -d {_env('DB_NAME', 'ai_recruiter')} -f alembic/bootstrap.sql\n"
        )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def ensure_role(cur, role: str, password: str) -> None:
    """Create the application login role if missing; keep its password in sync."""
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
    exists = cur.fetchone() is not None
    if not exists:
        cur.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD %s").format(sql.Identifier(role)),
            (password,),
        )
        print(f"  ✓ created role '{role}'")
    else:
        cur.execute(
            sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD %s").format(sql.Identifier(role)),
            (password,),
        )
        print(f"  ✓ role '{role}' already exists (password synced)")


def ensure_database(cur, dbname: str, owner: str) -> None:
    """Create the application database if missing (CREATE DATABASE can't be transactional)."""
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
    if cur.fetchone() is None:
        cur.execute(
            sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(dbname), sql.Identifier(owner)
            )
        )
        print(f"  ✓ created database '{dbname}'")
    else:
        print(f"  ✓ database '{dbname}' already exists")


def run_bootstrap_sql(dbname: str) -> None:
    """Apply alembic/bootstrap.sql (grants + legacy-object cleanup) as superuser."""
    if not BOOTSTRAP_SQL.exists():
        sys.exit(f"✗ bootstrap SQL not found at {BOOTSTRAP_SQL}")
    sql_text = BOOTSTRAP_SQL.read_text()
    conn = _connect_super(dbname)
    try:
        with conn.cursor() as cur:
            cur.execute(sql_text)
        print(f"  ✓ applied {BOOTSTRAP_SQL.relative_to(SERVER_DIR)} to '{dbname}'")
    finally:
        conn.close()


def run_migrations() -> None:
    """Run `alembic upgrade head` in-process as the application role."""
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(SERVER_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVER_DIR / "alembic"))
    command.upgrade(cfg, "head")
    print("  ✓ alembic upgrade head")


def main() -> None:
    parser = argparse.ArgumentParser(description="Idempotent DB bootstrap for the voice agent.")
    parser.add_argument(
        "--no-migrate",
        action="store_true",
        help="Only create role/database and apply grants; skip `alembic upgrade head`.",
    )
    args = parser.parse_args()

    load_dotenv(override=True)

    role = _env("DB_USER", "ai_user")
    password = _env("DB_PASSWORD", "secure_password")
    dbname = _env("DB_NAME", "ai_recruiter")
    maintenance_db = _env("DB_SUPERUSER_DB", "postgres")

    print(f"Bootstrapping database '{dbname}' (role '{role}') at "
          f"{_env('DB_HOST', 'localhost')}:{_env('DB_PORT', '5432')}")

    # Steps 2 & 3 run against the maintenance DB (CREATE DATABASE needs this).
    conn = _connect_super(maintenance_db)
    try:
        with conn.cursor() as cur:
            ensure_role(cur, role, password)
            ensure_database(cur, dbname, role)
    finally:
        conn.close()

    # Step 4: grants + legacy cleanup must run against the target DB.
    run_bootstrap_sql(dbname)

    # Step 5: migrate as the unprivileged app role.
    if args.no_migrate:
        print("\n✓ Bootstrap complete (migrations skipped). Run `uv run alembic upgrade head` when ready.")
    else:
        run_migrations()
        print("\n✓ Database ready.")


if __name__ == "__main__":
    main()
