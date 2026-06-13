"""Shared pytest fixtures for the backend suite."""

import pytest


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema():
    """Create the DB schema before any test runs.

    Table creation normally happens in the app's lifespan (startup), which the
    TestClient doesn't trigger here. On a fresh DB (e.g. SQLite in CI) the tables
    wouldn't exist; this makes the suite self-contained regardless of backend.
    """
    import app.models  # noqa: F401 — register Job/Candidate on Base
    from app.database import Base, engine, run_migrations

    Base.metadata.create_all(bind=engine)
    try:
        run_migrations()  # idempotent additive ALTERs (no-ops once columns exist)
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Clear per-IP rate-limit windows before each test.

    The limiter windows are module-level singletons, so without this an
    upload/IQ-heavy test could exhaust another test's per-minute budget and make
    the suite order-dependent (TestClient requests all share one client IP).
    """
    from app.core.ratelimit import reset_rate_limits

    reset_rate_limits()
    yield
