"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { AppBackground } from "@/components/layout/AppBackground";

export default function HomePage() {
  return (
    <>
      <AppBackground />
      <main className="flex min-h-screen flex-col items-center justify-center p-8 text-center">
        <span className="mb-6 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-[0_12px_28px_-10px_var(--primary)]">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" />
            <path d="M12 12l8-4.5M12 12v9M12 12L4 7.5" />
          </svg>
        </span>
        <h1 className="mb-4 font-display text-5xl font-bold tracking-tight text-heading">AI Recruiter</h1>
        <p className="mb-8 max-w-prose text-muted-foreground">
          Manage job openings, screen candidate résumés, and review aptitude and interview results — all in one place.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/admin/dashboard"
            className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-3 font-semibold text-primary-foreground shadow-[0_12px_28px_-10px_var(--primary)] transition hover:opacity-90"
          >
            Admin dashboard <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            href="/applicant"
            className="glass-rail inline-flex items-center gap-2 rounded-xl px-5 py-3 font-semibold text-foreground transition hover:bg-foreground/[0.04]"
          >
            View open roles
          </Link>
        </div>
      </main>
    </>
  );
}
