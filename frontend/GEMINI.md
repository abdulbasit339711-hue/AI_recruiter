# AI-Recruiter — Frontend (Next.js 15)

Scope: documents `frontend/` — the Next.js 15 App Router admin dashboard plus the
applicant/interview UI. Whole-repo overview is in the root `CLAUDE.md`.

## Run

```bash
cd frontend
npm install
cp .env.example .env.local      # fill in BACKEND_URL, ADMIN_API_TOKEN, NEXT_PUBLIC_VOICE_URL
npm run dev                     # http://localhost:3000
npm run build && npm run start  # production
npm run lint
```

Stack: Next.js ^15, React 19, TypeScript 5, Tailwind v4, TanStack React Query, Zustand,
react-hook-form + zod, Radix UI, livekit-client, framer-motion / gsap, lucide-react.

## Data flow (important)

- The browser **never** talks to FastAPI directly. All admin traffic goes through the **same-origin Next proxy** `src/app/api/admin/[...path]/route.ts`, which injects the admin bearer token server-side and forwards to `BACKEND_URL`. That's why `lib/api.ts` sets `baseURL = "/api/admin"`.
- `BACKEND_URL` and `ADMIN_API_TOKEN` are **server-only** env (never `NEXT_PUBLIC_`). `ADMIN_API_TOKEN` must equal the backend's.
- The interview page talks **directly** to the voice service at `NEXT_PUBLIC_VOICE_URL` (:7860) — that origin is intentionally browser-exposed.
- Login posts to `src/app/api/login/route.ts`; `middleware.ts` gates authenticated routes.

## Layout (`src/`)

- `app/` — App Router routes: `admin/` (dashboard), `applicant/[jobId]/apply` (+ `success`), `interview/`, `login/`, and `api/` proxy routes. Plus `layout.tsx`, `globals.css`.
- `components/` — `admin/` (JobCard, CandidateList, ScoreVisualization…), `candidates/` (InterviewPanel…), `job/`, `layout/`, `ui/` (Radix-based primitives), `providers.tsx` (React Query + theme providers).
- `hooks/` — one hook per server resource, each wrapping React Query: `useJobs`, `useJob`, `useCreateJob`, `useUpdateJob`, `useArchiveJob`, `useCandidates`, `useCandidate`, `useCandidateEvaluation`, `useUploadResume`, `useMetrics`, `useInterviewLive`, `useJobEvaluationEvents`. The `*Events`/`*Live` hooks subscribe to the backend SSE `/events` streams.
- `lib/` — `api.ts` (central axios client through the proxy), `voice.ts` (livekit client → voice service), `csv.ts` (export), `utils.ts`.
- `store/recruiter-store.ts` — Zustand client-side UI state.
- `types/index.ts` — shared TS types mirroring backend schemas.

## Conventions

- Add a backend call by extending `lib/api.ts` and wrapping it in a `hooks/use*.ts` React Query hook — components consume hooks, never axios directly.
- Server state = React Query; ephemeral UI state = Zustand. Don't copy server data into the store.
- Keep secrets server-side: only `NEXT_PUBLIC_*` vars reach the browser.

## Environment (`.env.local`)

```
NEXT_PUBLIC_VOICE_URL=http://127.0.0.1:7860   # browser-exposed: voice service origin
BACKEND_URL=http://127.0.0.1:8000             # server-only: FastAPI origin the proxy forwards to
ADMIN_API_TOKEN=...                           # server-only: MUST match the backend's token
```


---
_This file mirrors `CLAUDE.md` in this directory. The three agent guides (`CLAUDE.md`, `GEMINI.md`, `ANTIGRAVITY.md`) are kept identical — update all three together._
