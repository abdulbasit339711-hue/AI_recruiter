---
name: nextjs-app
description: >
  Build industry-grade Next.js 15 applications with App Router, TypeScript, Tailwind CSS v4,
  shadcn/ui, animations (Framer Motion + GSAP), and production-ready architecture. Use this
  skill whenever the user asks to build, scaffold, or improve a Next.js app, website, dashboard,
  landing page, SaaS product, or any React-based full-stack project — even if they just say
  "build me a website", "make a Next.js app", or "create a landing page". Also trigger for
  requests involving animations, page transitions, scroll effects, or visually rich React UIs.
  This skill covers everything from project setup to deployment-ready code with world-class design.
---

# Next.js Industry-Grade App Builder

This skill produces **production-ready, visually stunning Next.js 15 apps** — not boilerplate.
Every output should feel premium: fast, animated, beautifully designed, and architecturally sound.

---

## 1. Core Stack (Always Use)

| Layer | Choice | Why |
|---|---|---|
| Framework | **Next.js 15** (App Router) | RSC, streaming, edge-ready |
| Language | **TypeScript 5** (strict mode) | Type safety at scale |
| Styling | **Tailwind CSS v4** | Zero-config, CSS-first |
| Components | **shadcn/ui** (New York style) | Accessible, composable, un-opinionated |
| Animations | **Framer Motion** + **GSAP** | See Animation section |
| State | **Zustand** (global) + React state (local) | Lightweight, minimal boilerplate |
| Forms | **React Hook Form** + **Zod** | Type-safe validation |
| Dark Mode | **next-themes** | Zero hydration flicker |
| Fonts | **next/font** | No layout shift, self-hosted |

### Bootstrap Command
```bash
npx create-next-app@latest my-app \
  --typescript --tailwind --eslint --app --src-dir \
  --import-alias "@/*"

cd my-app
npx shadcn@latest init        # New York style, CSS variables: Yes
npm install framer-motion gsap @gsap/react
npm install zustand react-hook-form zod @hookform/resolvers
npm install next-themes lucide-react
```

---

## 2. Project Structure

```
src/
├── app/                        # App Router root
│   ├── layout.tsx              # Root layout: fonts, providers, metadata
│   ├── page.tsx                # Home route
│   ├── globals.css             # Tailwind + CSS variables
│   ├── (marketing)/            # Route group — public pages
│   │   ├── about/page.tsx
│   │   └── pricing/page.tsx
│   ├── (dashboard)/            # Route group — authenticated pages
│   │   ├── layout.tsx          # Sidebar, auth guard
│   │   └── dashboard/page.tsx
│   └── api/                    # Route Handlers
│       └── [...]/route.ts
├── components/
│   ├── ui/                     # shadcn auto-generated components
│   ├── layout/                 # Header, Footer, Sidebar, Nav
│   ├── sections/               # Page sections (Hero, Features, CTA)
│   └── shared/                 # Reusable cross-app components
├── lib/
│   ├── utils.ts                # cn() helper + shared utilities
│   ├── validators/             # Zod schemas
│   └── hooks/                  # Custom React hooks
├── store/                      # Zustand stores
├── types/                      # Global TypeScript interfaces
└── config/                     # Site config, nav links, metadata
```

---

## 3. Architecture Rules

### Server vs Client Components
- **Default to Server Components** — they reduce JS bundle and improve LCP.
- Add `"use client"` only when you need: state, effects, event handlers, browser APIs, or animation libraries.
- Never import GSAP or Framer Motion in Server Components.
- Keep data fetching in Server Components; pass data as props to Client Components.

```tsx
// ✅ Server Component — fetches data, no "use client"
export default async function ProductsPage() {
  const products = await fetchProducts(); // direct async/await
  return <ProductList products={products} />;
}

// ✅ Client Component — only for interactivity
"use client";
export function ProductList({ products }) {
  const [filter, setFilter] = useState("all");
  // ...
}
```

### Rendering Strategy Decision Tree
- **Static (SSG)**: Marketing pages, blogs, docs → `generateStaticParams` + no fetch options
- **SSR**: Auth-gated pages, user-specific content → `export const dynamic = "force-dynamic"`
- **ISR**: Product/content pages that change occasionally → `revalidate: 3600`
- **Streaming**: Data-heavy dashboards → Wrap in `<Suspense>` with skeleton fallback

### Route Groups
Use `(groupName)/` folders to apply different layouts without affecting URL:
```
app/
  (marketing)/layout.tsx   ← marketing header/footer
  (app)/layout.tsx         ← sidebar + auth
```

---

## 4. Animation System

### Philosophy: Two-Library Strategy
- **Framer Motion** → UI state transitions, component enter/exit, gesture-driven UIs
- **GSAP** → Scroll-driven sequences, complex timelines, stagger effects, SVG morphing

### Framer Motion — UI Animations
```tsx
"use client";
import { motion, AnimatePresence } from "framer-motion";

// Page transition wrapper
export const PageTransition = ({ children }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -20 }}
    transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}
  >
    {children}
  </motion.div>
);

// Staggered list reveal
export const staggerContainer = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1, delayChildren: 0.2 } }
};
export const fadeInUp = {
  hidden: { opacity: 0, y: 40 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } }
};
```

### GSAP — Scroll & Complex Animations
```tsx
"use client";
import { useEffect, useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

export function ScrollRevealSection({ children }) {
  const ref = useRef(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo(".reveal-item",
        { opacity: 0, y: 60 },
        {
          opacity: 1, y: 0,
          duration: 0.8,
          stagger: 0.15,
          ease: "power3.out",
          scrollTrigger: {
            trigger: ref.current,
            start: "top 80%",
            toggleActions: "play none none reverse"
          }
        }
      );
    }, ref);
    return () => ctx.revert(); // ← always clean up
  }, []);

  return <section ref={ref}>{children}</section>;
}
```

### Animation Performance Rules
1. Always clean up with `ctx.revert()` (GSAP) or proper unmount
2. Use `will-change: transform` sparingly — only on actively animating elements
3. Prefer `transform` and `opacity` (GPU-composited) over `width`, `height`, `top`, `left`
4. Lazy-load heavy animation components: `dynamic(() => import("./HeroAnimation"), { ssr: false })`
5. Respect `prefers-reduced-motion`:
```tsx
const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
```

---

## 5. Visual Design System

### Design Thinking First
Before writing a single line of code, commit to a bold aesthetic direction:
- **Purpose**: Who uses this? What's the emotional tone?
- **Aesthetic**: Pick one extreme and own it — brutalist/raw, soft/luxury, editorial, futuristic, organic
- **Signature moment**: What's the one animation or visual detail users will remember?

### Typography
Use `next/font` — never CDN. Pair a distinctive display font with a refined body font:
```tsx
// app/layout.tsx
import { Playfair_Display, DM_Sans } from "next/font/google";

const display = Playfair_Display({ subsets: ["latin"], variable: "--font-display" });
const body = DM_Sans({ subsets: ["latin"], variable: "--font-body" });
```
Avoid: Inter, Roboto, Arial. Prefer: Sora, Cabinet Grotesk, Clash Display, Playfair Display, Geist.

### Color & Theme (CSS Variables)
```css
/* globals.css */
@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222 84% 5%;
    --primary: 262 83% 58%;       /* vivid purple */
    --accent: 38 92% 50%;         /* electric amber */
    --radius: 0.75rem;
  }
  .dark {
    --background: 222 84% 5%;
    --foreground: 210 40% 98%;
  }
}
```

### Backgrounds & Atmosphere
Create depth — never flat solid colors:
```css
/* Gradient mesh background */
background: radial-gradient(ellipse 80% 50% at 50% -20%, hsl(var(--primary)/0.3), transparent),
            radial-gradient(ellipse 60% 40% at 80% 80%, hsl(var(--accent)/0.2), transparent),
            hsl(var(--background));

/* Noise texture overlay */
&::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,..."); /* SVG noise */
  opacity: 0.04;
  pointer-events: none;
}
```

### Micro-interactions Checklist
- Hover states on all interactive elements (scale, glow, underline)
- Focus-visible styles (never remove outlines — make them beautiful)
- Loading skeletons (not spinners) for async data
- Page transitions via Framer Motion `AnimatePresence`
- Magnetic cursor effects on hero CTAs (optional, high impact)

---

## 6. Performance Standards

### Core Web Vitals Targets
| Metric | Target |
|---|---|
| LCP | < 2.5s |
| INP | < 200ms |
| CLS | < 0.1 |
| Bundle (initial JS) | < 150kb gzipped |

### Key Optimizations
```tsx
// Images — always use next/image
import Image from "next/image";
<Image src="/hero.jpg" alt="Hero" width={1200} height={600} priority />

// Dynamic imports for heavy components
const Globe = dynamic(() => import("@/components/Globe"), {
  ssr: false,
  loading: () => <Skeleton className="h-96 w-full" />
});

// Font: no FOUT
import { GeistSans } from "geist/font/sans";
```

### Metadata Pattern
```tsx
// app/layout.tsx
export const metadata: Metadata = {
  title: { default: "App Name", template: "%s | App Name" },
  description: "...",
  openGraph: { type: "website", images: ["/og.jpg"] },
  twitter: { card: "summary_large_image" },
};
```

---

## 7. Common Patterns

### Hero Section (with animation)
```tsx
"use client";
import { motion } from "framer-motion";

export function Hero() {
  return (
    <section className="relative min-h-screen flex items-center overflow-hidden">
      {/* Animated background */}
      <div className="absolute inset-0 -z-10 [background:radial-gradient(ellipse_80%_50%_at_50%_-20%,hsl(var(--primary)/0.25),transparent)]" />
      
      <div className="container mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.25, 0.46, 0.45, 0.94] }}
          className="max-w-4xl"
        >
          <motion.span
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="inline-flex items-center gap-2 text-sm font-medium text-primary border border-primary/20 rounded-full px-4 py-1.5 mb-6 bg-primary/5"
          >
            ✦ New: Feature announcement
          </motion.span>
          
          <h1 className="font-display text-6xl md:text-8xl font-bold tracking-tight leading-[0.9] mb-6">
            Build faster,<br />
            <span className="text-primary">ship better</span>
          </h1>
          
          <p className="text-xl text-muted-foreground max-w-xl mb-10 leading-relaxed">
            Description that explains the value clearly and concisely.
          </p>
          
          <div className="flex gap-4">
            <Button size="lg" className="group">
              Get started
              <ArrowRight className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform" />
            </Button>
            <Button size="lg" variant="outline">See demo</Button>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
```

### Animated Feature Cards
```tsx
"use client";
import { motion } from "framer-motion";

const features = [/* ... */];

export function Features() {
  return (
    <section className="py-24">
      <motion.div
        variants={{ show: { transition: { staggerChildren: 0.1 } } }}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, amount: 0.2 }}
        className="grid grid-cols-1 md:grid-cols-3 gap-6"
      >
        {features.map((f) => (
          <motion.div
            key={f.title}
            variants={{ hidden: { opacity: 0, y: 30 }, show: { opacity: 1, y: 0 } }}
            whileHover={{ y: -4 }}
            className="group p-6 rounded-2xl border border-border/50 bg-card hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5 transition-shadow"
          >
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center mb-4 group-hover:bg-primary/20 transition-colors">
              <f.icon className="h-5 w-5 text-primary" />
            </div>
            <h3 className="font-semibold text-lg mb-2">{f.title}</h3>
            <p className="text-muted-foreground text-sm leading-relaxed">{f.description}</p>
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}
```

### Root Layout with Providers
```tsx
// app/layout.tsx
import { ThemeProvider } from "next-themes";
import { GeistSans } from "geist/font/sans";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={GeistSans.variable}>
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
```

---

## 8. Data Fetching Patterns

```tsx
// Server Component — direct async fetch
async function Page() {
  const data = await fetch("https://api.example.com/data", {
    next: { revalidate: 3600 } // ISR
  });
  // ...
}

// Client Component — SWR or React Query
"use client";
import useSWR from "swr";
const { data, isLoading } = useSWR("/api/data");

// Server Actions — form mutations
"use server";
export async function createItem(formData: FormData) {
  const parsed = itemSchema.parse(Object.fromEntries(formData));
  await db.insert(items).values(parsed);
  revalidatePath("/items");
}
```

---

## 9. Deployment Checklist

Before shipping:
- [ ] `next build` passes with 0 errors and 0 TypeScript errors
- [ ] All images use `next/image` with explicit dimensions
- [ ] Metadata (title, description, OG) set on every page
- [ ] Dark mode tested, no hydration flash
- [ ] `prefers-reduced-motion` respected in all animations
- [ ] Lighthouse score: Performance >90, Accessibility >95
- [ ] Environment variables in `.env.local` and Vercel dashboard
- [ ] Error boundaries (`error.tsx`) on dynamic routes
- [ ] Loading states (`loading.tsx`) on slow data routes
- [ ] `robots.txt` and `sitemap.xml` generated (`app/robots.ts`, `app/sitemap.ts`)

### Vercel Deploy
```bash
npm i -g vercel
vercel --prod
```

---

## 10. Quick Reference

### Shadcn Component Add
```bash
npx shadcn@latest add button card dialog sheet tabs
```

### Essential File Templates
- `src/lib/utils.ts` — `cn()` helper (auto-created by shadcn)
- `src/config/site.ts` — site name, description, nav links
- `src/types/index.ts` — shared interfaces
- `src/store/app-store.ts` — Zustand global store

### Debug Tip
In `next.config.ts`, enable bundle analysis:
```ts
const withBundleAnalyzer = require("@next/bundle-analyzer")({
  enabled: process.env.ANALYZE === "true",
});
```
Run: `ANALYZE=true next build`

---

## 11. Project Integration: FastAPI Backend & Recruiter dashboard (Built-on Instructions)

### A. Context & State Management
When integrating Next.js 15 with our FastAPI Python Backend:
1. **React Query Providers**: Move the `QueryClientProvider` into a Client Component wrapper (e.g. `src/components/providers.tsx` with `"use client"`) to prevent hydration mismatch and server-side context errors in `layout.tsx`.
2. **Global Client State**: Use `Zustand` to manage active job filters, selected candidates, and general application theme or sidebar collapses.
3. **API Proxy/Routing**: Configure Next.js rewrites or a dedicated client-side API helper using Axios pointing to the FastAPI port (default `http://127.0.0.1:8000`).

### B. Dynamic Resume Ingestion
- Maintain state transitions during PDF uploads: `Pending` -> `Scoring` -> `Processed`.
- Show micro-animations (progress bar, loading skeletons) when scoring.
- Display ranking lists using staggered motion animations (`framer-motion`).

---

## 📝 ACTIVE TODO LIST & CONTEXT TRACKER

### Phase 1: Establish SKill.md and Project Setup
- [x] Create `SKill.md` containing Next.js 15 design rules and integration directives.
- [ ] Resolve hydration error in `frontend/src/app/layout.tsx` by setting up `src/components/providers.tsx` wrapper.
- [ ] Implement site metadata configuration in `src/config/site.ts`.

### Phase 2: Core Components & Layout
- [ ] Install missing Tailwind CSS, Radix UI, Framer Motion, and shadcn/ui components (Buttons, Cards, Dialogs, Select, Tabs, Progress, Skeletons).
- [ ] Build global Sidebar and Page Header using Outfit typography and modern dark-mode gradient patterns.
- [ ] Create layout transitions and page-level container animations.

### Phase 3: API Client & Zustand Store
- [ ] Create API hook wrappers (`axios` + `react-query`) for:
  - `GET /jobs` and `POST /jobs` (Create Job)
  - `PUT /jobs/{job_id}` and `DELETE /jobs/{job_id}` (Edit/Archive Job)
  - `POST /upload` (Upload PDF with `job_id`)
- [ ] Create `store/recruiter-store.ts` in Zustand to manage the `selectedJobId` and candidate selection.

### Phase 4: Job & Dashboard Interface
- [ ] Build the **Job Management Panel** (Create Job modal, Edit Job dialog, soft-archive toggle).
- [ ] Build the **Resume Upload Intake Zone** (drag-and-drop zone with file size guards).
- [ ] Build the **Candidate Leaderboard Table** (filtering by score, sorting, status tags, query re-process trigger).
- [ ] Build the **Candidate Profile Deep-Dive Panel** (visual progress bars for Tiers 1-3, LLM text summaries, list of evidence).
- [ ] Implement CSV and Markdown Report export download triggers.

### Phase 5: Verification & Deployment
- [ ] Build test locally with `npm run build` or `next build` to verify zero TS/Next compile errors.
- [ ] Verify CORS issues between FastAPI and Next.js.
