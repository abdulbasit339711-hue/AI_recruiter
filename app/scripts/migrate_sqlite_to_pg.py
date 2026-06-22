"""One-shot copy of jobs + candidates from a legacy SQLite DB into PostgreSQL.

Usage:
    # target is taken from DATABASE_URL (the new Postgres); source defaults to
    # the legacy sqlite file, override with --sqlite
    python -m app.scripts.migrate_sqlite_to_pg --sqlite sqlite:///ai_recruiter.db

Safe to run once. It preserves primary keys and copies jobs before candidates
(FK order). If the target already has rows for a table, that table is skipped.
"""

import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import DATABASE_URL, Base
import app.models as models


def _copy(model, src_session, dst_session) -> int:
    if dst_session.query(model).count() > 0:
        print(f"  {model.__tablename__}: target not empty, skipping")
        return 0
    rows = src_session.query(model).all()
    for row in rows:
        data = {c.name: getattr(row, c.name) for c in model.__table__.columns}
        dst_session.add(model(**data))
    dst_session.commit()
    print(f"  {model.__tablename__}: copied {len(rows)} rows")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", default="sqlite:///ai_recruiter.db", help="source SQLite URL")
    args = parser.parse_args()

    if not DATABASE_URL.startswith("postgresql"):
        raise SystemExit(f"DATABASE_URL must point at PostgreSQL, got: {DATABASE_URL}")

    src_engine = create_engine(args.sqlite, connect_args={"check_same_thread": False})
    dst_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    Base.metadata.create_all(bind=dst_engine)  # ensure target tables exist

    Src = sessionmaker(bind=src_engine)
    Dst = sessionmaker(bind=dst_engine)
    src, dst = Src(), Dst()
    try:
        print(f"Migrating {args.sqlite} -> {DATABASE_URL}")
        _copy(models.Job, src, dst)         # parent first
        _copy(models.Candidate, src, dst)   # then children (job_id FK)
        print("Done.")
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    main()
