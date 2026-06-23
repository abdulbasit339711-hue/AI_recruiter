"""Auth tests for the voice server's operator endpoints (runner.py).

Run from the server dir with the project venv:
    .venv/bin/python -m pytest test_voice_auth.py -v
"""

import os

import pytest

# The operator guard is OFF by default (open for local testing) and only enforced
# when VOICE_REQUIRE_AUTH is truthy — see runner._voice_auth_required(). These
# tests verify the guard's behaviour *when enabled*, so turn it on. Both flags are
# read lazily via os.getenv() at request time, so setting them here is sufficient.
os.environ["VOICE_REQUIRE_AUTH"] = "true"
os.environ["ADMIN_API_TOKEN"] = "voice-test-token"

from fastapi.testclient import TestClient  # noqa: E402

import runner  # noqa: E402

TOKEN = "voice-test-token"
client = TestClient(runner.app)


def test_protected_set_is_what_we_expect():
    assert ("POST", "/interview/configure") in runner._PROTECTED_VOICE_ROUTES
    assert ("POST", "/chat") in runner._PROTECTED_VOICE_ROUTES
    assert ("POST", "/settings") in runner._PROTECTED_VOICE_ROUTES
    assert ("POST", "/pipeline") not in runner._PROTECTED_VOICE_ROUTES


def test_chat_without_token_is_401():
    r = client.post("/chat", json={"text": "hi"})
    assert r.status_code == 401


def test_configure_without_token_is_401():
    r = client.post("/interview/configure", json={"candidate_id": 1, "job_id": 1})
    assert r.status_code == 401


def test_chat_with_wrong_token_is_401():
    r = client.post("/chat", json={"text": "hi"}, headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_chat_with_valid_token_passes_guard():
    # No bot is running, so the handler returns its own message — the point is that
    # the AUTH guard let the request THROUGH (not a 401/503).
    r = client.post("/chat", json={"text": "hi"}, headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code != 401
    assert r.status_code != 503


def test_validate_endpoint_is_public():
    # /interview/validate must not be blocked by the admin guard (it does its own
    # signed-token check and returns valid:false here).
    r = client.get("/interview/validate", params={"token": "garbage"})
    assert r.status_code == 200
    assert r.json().get("valid") is False
