# Frontend Brief — AI-Recruiter (Needs vs Nice-to-haves)

A ready-to-paste prompt / requirements brief for building or improving the AI-Recruiter
frontend. Separates must-have **Needs** from **Nice-to-haves**. Companion to
`FRONTEND_IMPROVEMENT_PROMPT.md` (which is the issue-driven improvement version).

---

## PROMPT

You are building/improving the **frontend** of **AI-Recruiter**, a recruitment platform with
an **HR admin dashboard** and a **public applicant flow**. Deliver a polished, accessible,
consistent UI **without changing backend API contracts or the security model**.

### Context & stack (keep these foundations)
- Next.js 15 (App Router), React 19, **TypeScript strict**, Tailwind v4, Radix UI, TanStack
  React Query (server state), Zustand (UI state), framer-motion, lucide-react.
- All admin traffic goes through the same-origin proxy `app/api/admin/[...path]/route.ts`
  (injects the admin token server-side). **Never** expose secrets / `BACKEND_URL` /
  `ADMIN_API_TOKEN` to the client; only `NEXT_PUBLIC_*` reaches the browser.
- Pattern: add to `lib/api.ts` -> wrap in a `hooks/use*.ts` React Query hook -> components
  consume hooks. Server state = React Query (don't mirror into Zustand). Reuse
  `components/ui/` Radix primitives.
- Live updates use a reconnecting EventSource (`lib/sse.ts`) — preserve it.

### The two surfaces
- **HR dashboard** (`app/admin/...`): jobs list, candidates leaderboard (table + Kanban),
  candidate **detail drawer**, score visualization, CSV export, interview panel.
- **Applicant flow** (`app/applicant/[jobId]/apply`): a 2-step flow — timed **aptitude (IQ)
  screen** then résumé upload — plus the live **interview page** (LiveKit), and **login**.

---

### NEEDS (must-have — the build is not done without these)

**Functional**
1. HR can browse jobs and, per job, see a ranked candidate list with: effective score, tier
   1/2/3 breakdown, status + HR-status, **IQ score with accuracy and time**, submitted date.
2. A **sortable, scannable** candidate table — sortable by effective score, IQ, and date;
   with a dedicated, visible **IQ column** (not buried).
3. A candidate **detail view** showing: scores, **profile (role, companies, experience,
   skills)**, evidence/summary, **IQ per-question breakdown** (each question, answered-vs-
   correct, per-question time), interview results, notes, and HR actions (status change,
   score override, add note, send invite, download report).
4. Applicant flow: clear **2-step progress** (aptitude -> upload), one timed question at a
   time with a visible countdown, a reassuring upload step, and a clean **IQ result summary**
   (score, accuracy, time) before upload. Must **never block** the application if the IQ
   screen errors.
5. Live evaluation/interview updates reflect in the UI in real time (SSE) and **auto-
   reconnect** on a network blip.

**Quality (non-negotiable)**
6. **Every view has proper loading (skeletons), empty, and error states**; actions disable
   while pending and surface backend error detail.
7. **Accessibility:** full keyboard nav, focus trap/restore in dialogs, ARIA labels on
   icon-only buttons, sufficient dark-theme contrast, `aria-live` for countdown/toasts, and
   `prefers-reduced-motion` respected.
8. **Responsive / mobile-first** — the applicant flow works well on phones; the dashboard
   degrades gracefully on small/medium widths.
9. **Consistency:** one spacing scale, unified badge/button variants, and shared
   number/date/**duration** formatting (`lib/utils.ts` has `formatDuration`).
10. **Stays green:** `npx tsc --noEmit`, `npm run lint`, and `npm run build` all pass; secret
    model, React Query conventions, and SSE behavior preserved.

---

### NICE-TO-HAVES (do if time allows; propose before large ones)

- **Dedicated candidate page** (`/admin/candidates/[id]`) with tabs (Overview · IQ breakdown
  · Interview · Notes) to replace the cramped drawer.
- **IQ breakdown polish:** expandable/collapsible questions, color-coded correct/incorrect,
  and a small per-question time bar.
- **Bulk actions** on the candidate table (multi-select -> status change / export / invite).
- **Filtering & search** improvements: combine status + HR-status + score range + IQ range;
  persist in the URL.
- **Charts:** score distribution, IQ vs résumé-score scatter, funnel by HR-status.
- **Design-token pass:** formalize `globals.css` variables into a documented theme scale;
  optional light/dark toggle.
- **Optimistic updates** for status/notes with rollback on failure.
- **Component tests** (Testing Library) for the candidate table, IQ test, and drawer;
  optionally Storybook for `components/ui/`.
- **Micro-interactions:** subtle transitions, toast refinements, copy-to-clipboard on
  interview links, keyboard shortcuts (e.g. `j/k` to move rows, `Enter` to open).
- **i18n scaffolding** and an export-to-PDF improvement for the candidate report.

---

### How to work
1. Run the app, then list the **top 8–10 concrete issues** (file + one-line fix) and confirm
   priorities.
2. Ship **small, reviewable commits**, one surface at a time; verify each in the browser
   (:3000) and keep tsc/lint/build green.
3. Don't regress the secret model, React Query conventions, or live SSE updates.

**Deliverable:** a polished, accessible, responsive dashboard + applicant flow, with a short
per-surface changelog and recommended follow-ups.
