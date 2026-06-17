"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { AppBackground } from "@/components/layout/AppBackground";
import { Stagger, StaggerItem } from "@/components/ui/motion";

export default function HomePage() {
  return (
    <>
      <AppBackground />
      <main className="flex min-h-screen flex-col items-center justify-center p-8 text-center">
        <Stagger className="flex flex-col items-center" gap={0.09} delay={0.1}>
          <StaggerItem>
            <span className="mb-6 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-[0_12px_28px_-10px_var(--primary)]">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" />
                <path d="M12 12l8-4.5M12 12v9M12 12L4 7.5" />
              </svg>
            </span>
          </StaggerItem>

          <StaggerItem>
            <p className="mb-3 font-mono text-xs uppercase tracking-[0.18em] text-muted-foreground">
              AI-assisted hiring
            </p>
          </StaggerItem>

          <StaggerItem>
            <h1 className="mb-4 max-w-3xl font-display text-5xl font-bold tracking-tight text-heading">
              Screen and shortlist candidates faster
            </h1>
          </StaggerItem>

          <StaggerItem>
            <p className="mb-8 max-w-prose text-muted-foreground">
              Post job openings, score résumés against each role, and review aptitude and interview results — all in one place.
            </p>
          </StaggerItem>

          <StaggerItem>
            <div className="flex flex-wrap items-center justify-center gap-3">
              <Link
                href="/admin/dashboard"
                className="group inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-3 font-semibold text-primary-foreground shadow-[0_12px_28px_-10px_var(--primary)] transition hover:opacity-90"
              >
                Admin dashboard
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <Link
                href="/applicant"
                className="glass-rail inline-flex items-center gap-2 rounded-xl px-5 py-3 font-semibold text-foreground transition hover:bg-foreground/[0.04]"
              >
                View open roles
              </Link>
            </div>
          </StaggerItem>
        </Stagger>
      </main>
    </>
  );
}
