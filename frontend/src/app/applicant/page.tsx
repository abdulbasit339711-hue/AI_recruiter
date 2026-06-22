// src/app/applicant/page.tsx
"use client";

import React from "react";
import { useJobs } from "@/hooks/useJobs";
import { ApplicantJobCard } from "@/components/applicant/ApplicantJobCard";
import { AnimatePresence } from "framer-motion";
import { FadeIn, Stagger, StaggerItem } from "@/components/ui/motion";

const ORG_NAME = process.env.NEXT_PUBLIC_ORG_NAME || "Us";

export default function ApplicantJobListing() {
  const { data: jobs, isLoading, isError, error } = useJobs();

  if (isLoading) {
    return (
      <section className="mx-auto grid max-w-6xl grid-cols-1 gap-6 p-4 py-8 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-48 animate-pulse glass rounded-2xl" />
        ))}
      </section>
    );
  }

  if (isError) {
    return (
      <div className="p-4 text-center text-weak">
        Failed to load jobs: {error instanceof Error ? error.message : "Unknown error"}
      </div>
    );
  }

  return (
    <section className="mx-auto max-w-6xl space-y-7 p-4 py-8">
      <FadeIn y={18}>
        <p className="font-mono text-xs uppercase tracking-[0.06em] text-muted-foreground">
          Careers at {ORG_NAME}
        </p>
        <h1 className="mt-2 font-display text-[34px] font-bold leading-tight tracking-tight text-heading">
          Open roles
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Find a role that fits and submit your résumé. Every application starts with a short
          aptitude screen — no account required.
        </p>
      </FadeIn>

      <Stagger className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3" gap={0.06} delay={0.1}>
        <AnimatePresence>
          {jobs?.map((job) => (
            <StaggerItem key={job.id}>
              <ApplicantJobCard job={job} />
            </StaggerItem>
          ))}
          {jobs?.length === 0 && (
            <p className="col-span-full text-sm text-muted-foreground">
              No open roles right now — check back soon.
            </p>
          )}
        </AnimatePresence>
      </Stagger>
    </section>
  );
}
