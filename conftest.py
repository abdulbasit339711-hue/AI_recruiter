"""Root pytest conftest — isolate the suite from the real database.

Backend tests create jobs/candidates with no rollback. Run against the shared
Postgres (the .env DATABASE_URL) they leave noise behind (e.g. dozens of 'IQ Job'
rows). This forces every test session onto a fresh, throwaway SQLite file BEFORE
`app.database` reads the env, so tests are isolated and repeatable and never touch
the real DB. Set KEEP_TEST_DB=1 to opt out (e.g. to run against a specific DB).

Must live at the repo root so pytest imports it before collecting test modules
(which import `app`, triggering the engine creation).
"""

import atexit
import os
import tempfile

if not os.environ.get("KEEP_TEST_DB"):
    _fd, _path = tempfile.mkstemp(prefix="ai_recruiter_test_", suffix=".db")
    os.close(_fd)
    os.environ["DATABASE_URL"] = f"sqlite:///{_path}"
    atexit.register(lambda: os.path.exists(_path) and os.remove(_path))

# Signing secrets are now fail-closed in prod (no hardcoded dev fallback), so the
# suite must supply its own. setdefault keeps any value the developer already exported.
os.environ.setdefault("IQ_TEST_SECRET", "test-only-iq-secret")
os.environ.setdefault("INTERVIEW_LINK_SECRET", "test-only-interview-link-secret")
