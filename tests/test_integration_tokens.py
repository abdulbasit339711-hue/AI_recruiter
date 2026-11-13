"""Per-customer integration tokens: scoped to one org, revocable, never the admin token."""

import importlib

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

import app.core.auth as auth
from app.core import integration_tokens as it
from app.core.utils import _utcnow
from app.database import Base, SessionLocal, engine
from app.models import Candidate, Job, Org

ADMIN = "test-admin-token"


@pytest.fixture
def world(monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", ADMIN)
    importlib.reload(auth)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    now = _utcnow().isoformat()
    a, b = Org(slug=f"a-{now}", name="A", created_at=now), Org(slug=f"b-{now}", name="B", created_at=now)
    db.add_all([a, b]); db.commit()
    ja = Job(title="ja", department="d", job_description="x", org_id=a.id, created_at=now)
    jb = Job(title="jb", department="d", job_description="x", org_id=b.id, created_at=now)
    db.add_all([ja, jb]); db.commit()
    ca = Candidate(filename="f", raw_text="t", job_id=ja.id, created_at=now)
    cb = Candidate(filename="f", raw_text="t", job_id=jb.id, created_at=now)
    db.add_all([ca, cb]); db.commit()
    row, tok_a = it.create_token(db, a.id, "hrms-a")
    ids = dict(a=a.id, ja=ja.id, jb=jb.id, ca=ca.id, cb=cb.id, row=row.id)

    api = FastAPI()
    api.middleware("http")(auth.admin_token_guard)

    @api.post("/jobs")
    def create_job(request: Request):
        return {"org": getattr(request.state, "integration_org_id", None)}

    @api.get("/jobs/{i}/candidates")
    def lc(i: int): return {}

    @api.get("/candidates/{i}")
    def gc(i: int): return {}

    @api.post("/candidates/{i}/interview-invite")
    def inv(i: int): return {}

    @api.delete("/jobs/{i}")
    def dj(i: int): return {}

    @api.get("/metrics")
    def metrics(): return {}

    yield TestClient(api), tok_a, ids, db
    db.close()


def H(t): return {"Authorization": f"Bearer {t}"}


def test_scoped_to_own_org(world):
    c, tok, ids, _ = world
    assert c.get(f"/jobs/{ids['ja']}/candidates", headers=H(tok)).status_code == 200
    assert c.get(f"/candidates/{ids['ca']}", headers=H(tok)).status_code == 200
    assert c.post(f"/candidates/{ids['ca']}/interview-invite", headers=H(tok)).status_code == 200
    # other customer's data, and non-allowlisted routes, are refused
    assert c.get(f"/jobs/{ids['jb']}/candidates", headers=H(tok)).status_code == 403
    assert c.get(f"/candidates/{ids['cb']}", headers=H(tok)).status_code == 403
    assert c.delete(f"/jobs/{ids['ja']}", headers=H(tok)).status_code == 403
    assert c.get("/metrics", headers=H(tok)).status_code == 403
    # created jobs are forced into the token's org
    assert c.post("/jobs", headers=H(tok)).json() == {"org": ids["a"]}


def test_bad_token_and_admin_still_work(world):
    c, _, ids, _ = world
    assert c.get("/metrics", headers=H("air_nope")).status_code == 401
    assert c.get("/metrics").status_code == 401
    assert c.get("/metrics", headers=H(ADMIN)).status_code == 200
    assert c.get(f"/jobs/{ids['jb']}/candidates", headers=H(ADMIN)).status_code == 200


def test_revoked_token_rejected(world):
    c, tok, ids, db = world
    row = db.query(it.IntegrationToken).filter_by(id=ids["row"]).first()
    row.revoked_at = _utcnow().isoformat(); db.commit()
    assert c.get(f"/jobs/{ids['ja']}/candidates", headers=H(tok)).status_code == 401
