"""Shared-token authentication for HR/admin endpoints.

A single ``ADMIN_API_TOKEN`` (from the environment) gates every sensitive or
mutating endpoint. Clients present it as ``Authorization: Bearer <token>``.

This is intentionally simple — it suits an internal HR tool and adds no schema or
per-user identity. If/when real user accounts are needed, swap this out for a
JWT/session check without touching the call sites.

Fail-closed: if ``ADMIN_API_TOKEN`` is not configured, protected endpoints reject
all requests (503) rather than silently allowing access.

Enforcement is done with a single middleware (see ``main.py``) driven by a
path/method allowlist, so no individual route can be accidentally left
unprotected. ``require_admin`` is also provided for explicit per-route use.
"""

import hmac
import os
import re

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .ratelimit import admin_mutation_rate_ok

_bearer = HTTPBearer(auto_error=False)

# Endpoints reachable without the admin token. Everything else requires it.
#   - infra: root + health
#   - public apply flow: view a single job, submit a resume
_PUBLIC_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("GET", re.compile(r"^/?$")),
    ("GET", re.compile(r"^/health/?$")),
    ("GET", re.compile(r"^/jobs/?$")),            # careers listing (public job postings)
    ("GET", re.compile(r"^/jobs/\d+/?$")),        # view one job to apply
    ("GET", re.compile(r"^/iq-test/?$")),         # fetch the pre-application IQ test
    ("POST", re.compile(r"^/iq-test/submit/?$")), # submit IQ answers (scored server-side)
    ("POST", re.compile(r"^/upload/?$")),         # submit a resume
    ("GET",  re.compile(r"^/orgs/[^/]+/?$")),          # applicant portal: org branding by slug
    ("GET",  re.compile(r"^/orgs/[^/]+/jobs/?$")),     # applicant portal: org job listing
    ("GET",  re.compile(r"^/availability/[^/]+/?$")),  # candidate availability form
    ("POST", re.compile(r"^/availability/[^/]+/?$")),  # candidate submits availability
)


def _expected_token() -> str | None:
    token = os.getenv("ADMIN_API_TOKEN")
    return token.strip() if token else None


def is_public(method: str, path: str) -> bool:
    if method == "OPTIONS":  # let CORS preflight through
        return True
    return any(m == method and rx.match(path) for m, rx in _PUBLIC_RULES)


def token_is_valid(authorization: str | None) -> bool:
    """True if the Authorization header carries the configured admin bearer token."""
    expected = _expected_token()
    if not expected or not authorization:
        return False
    scheme, _, presented = authorization.partition(" ")
    if scheme.lower() != "bearer" or not presented:
        return False
    return hmac.compare_digest(presented.strip(), expected)


def auth_configured() -> bool:
    return _expected_token() is not None


async def admin_token_guard(request: Request, call_next):
    """ASGI middleware: require a valid admin bearer token on non-public endpoints.

    Registered in ``main.py`` via ``app.middleware("http")(admin_token_guard)``.
    Kept here (not as an inline closure) so it can be unit-tested directly.
    """
    if is_public(request.method, request.url.path):
        return await call_next(request)
    if not auth_configured():
        return JSONResponse(
            status_code=503,
            content={"detail": "Server auth is not configured (ADMIN_API_TOKEN unset)."},
        )
    if not token_is_valid(request.headers.get("authorization")):
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing or invalid admin credentials."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Authenticated, but the shared token must not be a license to spam mutations.
    if not admin_mutation_rate_ok(request.method, request):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please wait a moment and try again."},
            headers={"Retry-After": "60"},
        )
    return await call_next(request)


def require_admin(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """Explicit per-route dependency (503 if unconfigured, 401 if invalid)."""
    if not auth_configured():
        raise HTTPException(status_code=503, detail="Server auth is not configured (ADMIN_API_TOKEN unset).")
    presented = f"{creds.scheme} {creds.credentials}" if creds else None
    if not token_is_valid(presented):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid admin credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
