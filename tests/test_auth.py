"""Tests for the shared-admin-token auth (app/core/auth.py).

Covers the pure helpers (is_public / token_is_valid / auth_configured) and the
end-to-end middleware behaviour mounted on a minimal FastAPI app — so we exercise
the real guard without importing app.main (which loads ML models + a DB).
"""

import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.core.auth as auth


TOKEN = "test-secret-token"


@pytest.fixture
def client(monkeypatch):
    """Minimal app wired with the REAL admin_token_guard + the same public routes."""
    monkeypatch.setenv("ADMIN_API_TOKEN", TOKEN)
    importlib.reload(auth)  # re-read env if cached anywhere

    api = FastAPI()
    api.middleware("http")(auth.admin_token_guard)

    @api.get("/health")
    def health():
        return {"ok": True}

    @api.get("/jobs/{job_id}")
    def get_job(job_id: int):
        return {"job_id": job_id}

    @api.get("/jobs/{job_id}/candidates")
    def list_candidates(job_id: int):
        return {"job_id": job_id, "candidates": []}

    @api.post("/upload")
    def upload():
        return {"queued": True}

    @api.delete("/jobs/{job_id}")
    def delete_job(job_id: int):
        return {"deleted": job_id}

    return TestClient(api)


# --- pure helpers -----------------------------------------------------------

def test_is_public_allowlist():
    assert auth.is_public("GET", "/")
    assert auth.is_public("GET", "/health")
    assert auth.is_public("GET", "/jobs")            # careers listing (public postings)
    assert auth.is_public("GET", "/jobs/5")          # view one job to apply
    assert auth.is_public("POST", "/upload")
    assert auth.is_public("OPTIONS", "/jobs/5/candidates")  # CORS preflight


def test_is_public_rejects_protected():
    assert not auth.is_public("GET", "/metrics")              # dashboard metrics
    assert not auth.is_public("GET", "/jobs/5/candidates")     # candidate list
    assert not auth.is_public("DELETE", "/jobs/5")             # mutating
    assert not auth.is_public("GET", "/candidates/5/resume")   # PII
    assert not auth.is_public("POST", "/jobs/5/email")


def test_token_is_valid(monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", TOKEN)
    assert auth.token_is_valid(f"Bearer {TOKEN}")
    assert auth.token_is_valid(f"bearer {TOKEN}")          # scheme case-insensitive
    assert not auth.token_is_valid(f"Bearer {TOKEN}x")     # wrong token
    assert not auth.token_is_valid(TOKEN)                  # missing scheme
    assert not auth.token_is_valid("Basic abc")            # wrong scheme
    assert not auth.token_is_valid(None)


def test_auth_unconfigured(monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    assert not auth.auth_configured()
    assert not auth.token_is_valid(f"Bearer {TOKEN}")


# --- middleware integration -------------------------------------------------

def test_public_routes_need_no_token(client):
    assert client.get("/health").status_code == 200
    assert client.get("/jobs/7").status_code == 200
    assert client.post("/upload").status_code == 200


def test_protected_route_without_token_is_401(client):
    r = client.get("/jobs/7/candidates")
    assert r.status_code == 401
    assert r.headers.get("WWW-Authenticate") == "Bearer"


def test_protected_route_with_wrong_token_is_401(client):
    r = client.delete("/jobs/7", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_protected_route_with_valid_token_passes(client):
    r = client.get("/jobs/7/candidates", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    assert r.json()["job_id"] == 7

    r = client.delete("/jobs/7", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200


def test_fail_closed_when_unconfigured(monkeypatch):
    """No ADMIN_API_TOKEN -> protected routes return 503, never open access."""
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    importlib.reload(auth)
    api = FastAPI()
    api.middleware("http")(auth.admin_token_guard)

    @api.get("/jobs/{job_id}/candidates")
    def list_candidates(job_id: int):
        return {"job_id": job_id}

    @api.get("/health")
    def health():
        return {"ok": True}

    c = TestClient(api)
    assert c.get("/jobs/1/candidates").status_code == 503  # fail closed
    assert c.get("/health").status_code == 200             # public still works
