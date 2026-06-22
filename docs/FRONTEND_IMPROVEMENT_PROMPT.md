# Prompt — Frontend Betterment (AI-Recruiter dashboard)

Copy-paste the block below to an AI coding agent (or use as a design brief). It's grounded
in this repo's actual stack and current state so the agent doesn't have to rediscover it.

---

## PROMPT

You are improving the **frontend** of AI-Recruiter, a recruitment platform. Your job is to
raise the **UX quality, visual polish, accessibility, and consistency** of the Next.js HR
dashboard and the public applicant flow — **without changing backend contracts or the
security model**.

### Stack & architecture (do not change these foundations)
- Next.js 15 (App Router), React 19, TypeScript **strict mode on**, Tailwind v4
  (`@import "tailwindcss"`, `@tailwindcss/postcss`), Radix UI primitives, TanStack React
  Query (server state), Zustand (ephemeral UI state), framer-motion, lucide-react.
- **All admin API traffic goes through the same-origin proxy** `src/app/api/admin/[...path]/route.ts`,
  which injects the admin token server-side. Never put secrets or `BACKEND_URL`/
  `ADMIN_API_TOKEN` in client code; only `NEXT_PUBLIC_*` may reach the browser.
- Data-fetching convention: extend `lib/api.ts`, wrap in a `hooks/use*.ts` React Query hook;
  components consume hooks, never axios directly. Server state = React Query; don't copy it
  into Zustand.
- Keep it building: `npm run lint`, `npx tsc --noEmit`, and `npm run build` must stay clean.

### Key surfaces to improve
- **HR dashboard** (`src/app/admin/...`): jobs list, **candidates** leaderboard (table +
  Kanban views in `components/admin/CandidateTable.tsx` / `KanbanBoard.tsx`), a dense
  candidate **detail drawer** (a Radix Dialog in `app/admin/candidates/page.tsx`), score
  visualization, CSV export, interview panel.
- **Applicant flow** (`src/app/applicant/[jobId]/apply`): a 2-step flow — an **aptitude (IQ)
  screen** (`components/applicant/IqTest.tsx`, one timed question at a time) then résumé
  upload. Plus the live **interview page** (`app/interview/[token]`, LiveKit video/audio).
- **Login** (`app/login`).

### Known rough edges (fix these; verify against the running app)
1. **Information density / hierarchy.** The candidate detail drawer crams effective score,
   tier breakdown, IQ block (now with a per-question breakdown: question, answered-vs-correct,
   per-question time), profile (role/companies/experience/skills), evidence, interview
   questions, notes, and actions into one scroll. Introduce clear sections/tabs, better
   spacing, and visual grouping.
2. **IQ is hard to find.** The IQ score/time is a tiny grey line tucked under "Tier Scores"
   in the table. Consider a **dedicated, sortable "IQ" column** and a cleaner, expandable
   per-question breakdown in the drawer.
3. **Empty/loading/error states.** Audit every view for skeletons, empty states ("no
   candidates yet"), and friendly error states. Some actions don't disable while pending.
4. **Accessibility.** Keyboard navigation, focus management in the Dialog/drawer, ARIA labels
   on icon-only buttons, color-contrast on the dark theme, `aria-live` for the IQ countdown
   and toasts, and respecting `prefers-reduced-motion` for the framer/gsap animations.
5. **Responsive design.** The table and Kanban should degrade gracefully on smaller widths;
   the applicant flow should be mobile-first (candidates apply on phones).
6. **Consistency.** Unify spacing scale, badge styles (status vs HR-status), button variants,
   and number/date/duration formatting (a `formatDuration` helper already exists in
   `lib/utils.ts`).
7. **Applicant polish.** The aptitude screen and upload steps should feel reassuring and
   progress-clear; show the IQ result (score, accuracy, time) cleanly before upload.

### Constraints & guardrails
- Don't alter API request/response shapes or the proxy's public allowlist.
- Reuse existing primitives in `components/ui/` (Radix-based) rather than adding new UI libs.
- Keep bundle size in mind; prefer CSS/Tailwind over new heavy dependencies.
- Preserve the SSE live-update behavior (`hooks/useInterviewLive.ts`,
  `useCandidateEvaluation.ts`, `useJobEvaluationEvents.ts`, which use a reconnecting
  EventSource wrapper in `lib/sse.ts`).

### How to work
1. Start by running the app and listing the **top 8–10 concrete UX/a11y issues** you see,
   each with the file and a one-line fix plan. Get the highest-impact ones agreed first.
2. Make changes in **small, reviewable commits**, one surface at a time.
3. After each change: `npx tsc --noEmit`, `npm run lint`, `npm run build` must pass; verify
   the change in the browser (the app runs on :3000).
4. Don't regress the secret model, the React Query conventions, or the live SSE updates.

### Deliverable
A polished, accessible, consistent dashboard + applicant flow, with a short summary of what
changed per surface and any follow-ups you'd recommend (e.g. a design-token pass, a
component-test suite, Storybook).

---

## Optional add-ons (mention if you want the agent to scope them)
- A **design-token / theme pass** (formalize the CSS variables in `globals.css` into a
  documented scale).
- **Component tests** (Testing Library) for the candidate table, IQ test, and drawer.
- A **dedicated candidate detail page** (`/admin/candidates/[id]`) to replace/complement the
  cramped drawer, with the interview results, IQ breakdown, and profile as tabs.
