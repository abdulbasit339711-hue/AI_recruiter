# Running AI-Recruiter with Docker

The whole stack — FastAPI backend, Next.js frontend, Pipecat voice agent, and a
shared PostgreSQL — runs via `docker compose`.

## Quick start

```bash
cp .env.docker.example .env     # fill in API keys + secrets
docker compose up --build
```

| Service    | URL                       | Notes                                            |
|------------|---------------------------|--------------------------------------------------|
| frontend   | http://localhost:3000     | HR dashboard + applicant/interview UI            |
| backend    | http://localhost:8000     | FastAPI (`/docs` for OpenAPI)                    |
| voice      | http://localhost:7860     | Pipecat interview server (`runner:app`)          |
| postgres   | localhost:5433            | Shared DB (`jobs`/`candidates` + voice tables)   |

## Architecture in compose

```
browser ──► frontend:3000 ──(server-side /api/admin proxy)──► backend:8000
   │                                                              │
   └────────────────────► voice:7860                             │
                              │                                   │
                              └──────────► postgres:5432 ◄────────┘
                                          (shared: backend reads voice tables)
```

- The browser never calls FastAPI directly — the Next proxy injects `ADMIN_API_TOKEN`
  server-side and forwards to `BACKEND_URL` (`http://backend:8000`).
- The interview page talks **directly** to the voice service, so `NEXT_PUBLIC_VOICE_URL`
  must be the **host-reachable** origin (`http://localhost:7860`). It's inlined at
  build time, so changing it requires a frontend rebuild (`docker compose build frontend`).
- Backend and voice **share one Postgres**. Backend creates `jobs`/`candidates` and
  applies additive migrations in its lifespan; the voice container runs
  `alembic upgrade head` on boot for the interview tables.
- Interview-audio recordings live on the shared `recordings` named volume, mounted at
  `/data/recordings` in both backend and voice.

## Secrets that must match

`ADMIN_API_TOKEN` and `INTERVIEW_LINK_SECRET` are shared — set each once in `.env` and
compose passes the same value to backend, voice, and (for the token) the frontend proxy.

## Images

| Image                    | Dockerfile           | Build context | Base                         |
|--------------------------|----------------------|---------------|------------------------------|
| backend                  | `Dockerfile.backend` | repo root     | `python:3.12-slim`           |
| voice                    | `Dockerfile.voice`   | repo root     | `python:3.12-slim` + `uv`    |
| frontend                 | `frontend/Dockerfile`| `frontend/`   | `node:20-alpine` (standalone)|

The backend and voice images build from the **repo root** so they can pull in
`requirements.txt` and the editable `packages/shared` respectively.

> `voice-agent/server/Dockerfile` is the separate **Pipecat Cloud** image
> (`pcc-deploy.toml`); `Dockerfile.voice` at the root is the one compose uses.

## Common commands

```bash
docker compose up --build          # build + start everything
docker compose up -d               # start detached
docker compose logs -f voice       # tail one service
docker compose build frontend      # rebuild after changing NEXT_PUBLIC_VOICE_URL
docker compose down                # stop (keeps volumes)
docker compose down -v             # stop + wipe DB and recordings
```

## Notes

- The backend image adds `psycopg2-binary` (not in `requirements.txt`, which defaults to
  SQLite) so it can talk to the shared Postgres via `DATABASE_URL=postgresql+psycopg2://…`.
- The voice agent's optional YOLO proctoring detector auto-downloads its weights on first
  use; mount a `*.pt` file into the container if you want to pin them offline.
- LiveKit is an external (cloud) transport — set `LIVEKIT_URL/API_KEY/API_SECRET`; no
  local LiveKit container is run.
```
