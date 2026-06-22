# Frontend Brief — AI-Recruiter (Design + Build Prompt)

A ready-to-paste prompt for **redesigning and improving** the AI-Recruiter frontend. It
commits to a concrete aesthetic (**liquid glass**), a typography system, a color strategy,
and an explicit **non-technical-user** UX bar — then separates must-have **Needs** from
**Nice-to-haves**, and keeps the existing backend/security contracts untouched.

> **Tooling note for the agent:** this repo has the Anthropic **`frontend-design`** skill
> installed (user scope). It auto-activates on frontend work and pushes distinctive
> typography, bold-but-cohesive color, depth/atmosphere (layered translucency =
> glassmorphism), and high-impact motion, while banning generic AI aesthetics (Inter/Roboto,
> purple-on-white). Lean into it. Companion: `FRONTEND_IMPROVEMENT_PROMPT.md` (issue-driven
> version) and the Frontend Aesthetics Cookbook.

---

## PROMPT

You are **redesigning and improving** the **frontend** of **AI-Recruiter**, a recruitment
platform with an **HR admin dashboard** and a **public applicant flow**. The primary HR user
is **non-technical** — the UI must feel effortless, guided, and reassuring, never like a
developer tool. Deliver a polished, distinctive, accessible, consistent UI **without changing
backend API contracts or the security model**.

### Aesthetic direction — "Liquid glass, light base" (commit to this)

This is the one thing someone should remember about the product: **calm, premium depth**.

- **Surface language — frosted glass.** Primary panels (cards, drawers, the candidate detail,
  the IQ quiz card) are **translucent frosted-glass surfaces**: `backdrop-blur`, a subtle
  inner highlight (1px top border at low-opacity white), a soft layered drop shadow, and a
  faint 1px ring. Stack them at different blur/opacity levels so the UI reads as **layers of
  depth**, not flat cards.
- **3D & motion (high-impact, not noisy).** Subtle **card tilt / parallax on hover** (small
  rotateX/rotateY toward the cursor, ~4–6° max), gentle lift on hover, and **one
  well-orchestrated page-load** with **staggered reveals** (`animation-delay` / Motion
  stagger) beats scattered micro-interactions. Score numbers can **count up** on first paint.
  Use the **Motion** library (already a dep: `framer-motion`) for React; prefer CSS for
  simple transitions. **Every animation must respect `prefers-reduced-motion`** and degrade to
  instant.
- **Background = atmosphere, not a solid fill.** A **light, warm off-white base** with a faint
  **gradient mesh** and a low-opacity **noise/grain** overlay for texture. Decorative blurred
  color blobs behind the glass give the panels something to refract.
- **Depth over borders.** Prefer shadow, blur, and translucency to hard 1px dividers. Generous
  negative space. Let the glass do the separating.

### Color strategy (look into this carefully)

- **Light is the DEFAULT/base theme** — it's friendlier for a non-technical HR user and makes
  the glass read as clean and premium. **Dark mode is available via a visible toggle**
  (persisted, `next-themes` or a small `data-theme` + CSS-vars setup), **not** the forced base.
- **One dominant brand color with sharp, decisive accents** — avoid a timid, evenly-spread
  palette, and avoid the cliché purple-gradient-on-white. Reserve a single strong accent for
  primary actions and score emphasis; keep everything else quiet so data stands out.
- **Score semantics need their own scale:** a clear, color-blind-safe ramp for
  strong/medium/weak candidate scores (don't rely on red/green alone — pair with
  icon/label/shape). IQ accuracy and résumé tiers should be instantly legible at a glance.
- **All colors as CSS variables** in `globals.css`, with a documented light set and a dark set;
  components reference tokens, never raw hex. Verify **WCAG AA contrast in both themes**, and
  honor `prefers-reduced-transparency` (fall back to near-opaque panels).

### Typography (install via `next/font`, self-hosted)

- **Display / headings:** **Bricolage Grotesque** — warm, characterful, distinctive.
- **Body / UI:** **Geist Sans** — clean, modern, highly legible (NOT Inter/Roboto/system).
- **Numbers / scores / timers:** **Geist Mono** (tabular) so scores, IQ accuracy, and the
  countdown align and don't jitter.
- Establish a real **type scale** (display → h1…h4 → body → caption), consistent line-height
  and letter-spacing, and use weight/size — not color alone — for hierarchy.

### Non-technical-user UX bar (this is a NEED, not polish)

- **Plain language everywhere.** No jargon in the UI: prefer "Aptitude score", "Résumé match",
  "Strong / Promising / Weak" over "Tier 2", "semantic similarity", raw enum values. Keep
  internal terms in tooltips if needed.
- **Guided, not dense.** Progressive disclosure: show the headline (effective score, status,
  recommendation) first; tuck breakdowns behind clear "Show details" affordances.
- **Obvious primary action** on every screen, large hit targets, and **plain-language empty,
  loading, and error states that say what to do next** ("No candidates yet — share the apply
  link to start").
- **Helpful microcopy + tooltips** on any number or control that isn't self-evident
  (what the IQ score means, what an HR-status change does).
- **Confidence cues:** confirmations for destructive/outward actions (archive, invite),
  visible pending states, and friendly success toasts.

### Context & stack (keep these foundations)

- Next.js 15 (App Router), React 19, **TypeScript strict**, Tailwind v4
  (`@import "tailwindcss"`, `@tailwindcss/postcss`), Radix UI, TanStack React Query (server
  state), Zustand (UI state), framer-motion (Motion), lucide-react.
- All admin traffic goes through the same-origin proxy `app/api/admin/[...path]/route.ts`
  (injects the admin token server-side). **Never** expose secrets / `BACKEND_URL` /
  `ADMIN_API_TOKEN` to the client; only `NEXT_PUBLIC_*` reaches the browser.
- Pattern: add to `lib/api.ts` → wrap in a `hooks/use*.ts` React Query hook → components
  consume hooks. Server state = React Query (don't mirror into Zustand). Reuse and extend
  `components/ui/` Radix primitives rather than adding new UI libraries.
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
   1/2/3 breakdown (in plain language), status + HR-status, **IQ score with accuracy and
   time**, submitted date.
2. A **sortable, scannable** candidate table — sortable by effective score, IQ, and date;
   with a dedicated, visible **IQ column** (not buried in a grey sub-line).
3. A candidate **detail view** showing: scores, **profile (role, companies, experience,
   skills)**, evidence/summary, **IQ per-question breakdown** (each question, answered-vs-
   correct, per-question time), interview results, notes, and HR actions (status change,
   score override, add note, send invite, download report).
4. Applicant flow: clear **2-step progress** (aptitude → upload), one timed question at a
   time with a visible, calm countdown, a reassuring upload step, and a clean **IQ result
   summary** (score, accuracy, time) before upload. Must **never block** the application if
   the IQ screen errors.
5. Live evaluation/interview updates reflect in the UI in real time (SSE) and **auto-
   reconnect** on a network blip.

**Quality (non-negotiable)**
6. **Every view has proper loading (skeletons that match the glass surfaces), empty, and
   error states**; actions disable while pending and surface backend error detail in plain
   language.
7. **Accessibility:** full keyboard nav, focus trap/restore in dialogs, ARIA labels on
   icon-only buttons, AA contrast in **both** themes, `aria-live` for countdown/toasts,
   `prefers-reduced-motion` AND `prefers-reduced-transparency` respected.
8. **Responsive / mobile-first** — the applicant flow works well on phones (candidates apply
   on phones); the dashboard degrades gracefully on small/medium widths (table → cards).
9. **Consistency:** one spacing scale, one type scale, unified badge/button variants, shared
   number/date/**duration** formatting (`lib/utils.ts` has `formatDuration`), and the glass
   surface as a single reusable primitive (e.g. `components/ui/GlassCard`).
10. **Performance:** `backdrop-filter` is GPU-heavy — limit the number of simultaneously
    blurred layers, avoid blurring during scroll where it janks, and keep the page smooth on a
    mid-range laptop. Keep `npx tsc --noEmit`, `npm run lint`, and `npm run build` green;
    preserve the secret model, React Query conventions, and SSE behavior.

---

### NICE-TO-HAVES (do if time allows; propose before large ones)

- **Theme toggle polish:** animated light/dark switch with a remembered preference and a
  smooth cross-fade.
- **Dedicated candidate page** (`/admin/candidates/[id]`) with tabs (Overview · IQ breakdown ·
  Interview · Notes) to replace the cramped drawer.
- **IQ breakdown polish:** expandable/collapsible questions, color-coded (color-blind-safe)
  correct/incorrect, and a small per-question time bar.
- **Bulk actions** on the candidate table (multi-select → status change / export / invite).
- **Filtering & search:** combine status + HR-status + score range + IQ range; persist in URL.
- **Charts:** score distribution, IQ vs résumé-score scatter, funnel by HR-status — styled to
  match the glass aesthetic.
- **Design-token doc:** formalize the `globals.css` variables into a documented theme scale.
- **Optimistic updates** for status/notes with rollback on failure.
- **Component tests** (Testing Library) for the candidate table, IQ test, and drawer;
  optionally Storybook for `components/ui/`.
- **Micro-interactions:** copy-to-clipboard on interview links, keyboard shortcuts (`j/k` to
  move rows, `Enter` to open), refined toasts.
- **i18n scaffolding** and an export-to-PDF improvement for the candidate report.

---

### How to work

1. **Establish the design system first:** wire the fonts (`next/font`), define the CSS-variable
   color tokens (light default + dark), build the reusable **glass surface** primitive and the
   motion/reveal helpers (with reduced-motion fallbacks). Get this agreed before reskinning
   screens.
2. Then run the app and list the **top 8–10 concrete issues** (file + one-line fix) and confirm
   priorities.
3. Ship **small, reviewable commits**, one surface at a time; verify each in the browser
   (:3000) in **both light and dark**, on desktop and a phone width, and keep tsc/lint/build
   green.
4. Don't regress the secret model, React Query conventions, or live SSE updates.

**Deliverable:** a distinctive, accessible, responsive **liquid-glass** dashboard + applicant
flow (light default, dark toggle; Bricolage Grotesque + Geist; calm depth and motion) that a
non-technical HR user finds effortless — with a short per-surface changelog and recommended
follow-ups.
