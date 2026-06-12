"""Shared pytest fixtures for the backend suite."""

import pytest


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
