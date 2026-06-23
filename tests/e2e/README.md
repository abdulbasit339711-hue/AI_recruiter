# E2E browser tests

## interview_flow.mjs

Real-browser Playwright test covering the full interview lifecycle.

**Prerequisites**

```bash
# Full stack must be running
docker compose up -d

# Install Playwright + Chromium (one-time)
cd tests/e2e
npm init -y
npm install playwright
npx playwright install chromium
```

**Run**

```bash
# Mint a token (from repo root)
TOKEN=$(python3 -c "
import sys; sys.path.insert(0,'packages/shared/src')
from recruiter_shared import mint_invite_token
print(mint_invite_token(candidate_id=1, job_id=3,
  secret='ja-66GXFeBGNSWG2D7dpivo7J0GbJCoBGr8NkQ-GxKFvC6bS8hbZuFP_DrPgSrv4',
  ttl_minutes=120))
")

DISPLAY=:0.0 node tests/e2e/interview_flow.mjs "$TOKEN"
```

Screenshots land in `/tmp/` for inspection.

**What it covers**

- Admin login → candidate interview page → Overview score card + goals visible
- Assessment tab: Interview Goals panel present; post-call Evaluation Dimensions shown after session ends
- Transcript tab clickable
- Candidate interview link: token validates → pre-join screen shows role/name
- "Join now" → LiveKit connects → call UI goes live
- Mic button present in call controls
- Bot opening turn appears in transcript / captions
- Typed chat message delivered to voice service
- `/health` and `/events` SSE endpoint reachable
