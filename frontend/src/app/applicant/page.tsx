// src/app/applicant/page.tsx
"use client";

import React from "react";
import { useJobs } from "@/hooks/useJobs";
import { JobCard } from "@/components/job/JobCard";
import { motion, AnimatePresence } from "framer-motion";

export default function ApplicantJobListing() {
  const { data: jobs, isLoading, isError, error } = useJobs();

  if (isLoading) {
    // Simple skeleton grid
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
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.06em] text-muted-foreground">Careers</p>
        <h1 className="mt-2 font-display text-[34px] font-bold leading-tight tracking-tight text-heading">Open Roles</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Choose a role and submit a searchable PDF résumé. Every application starts with a short aptitude screen.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        <AnimatePresence>
          {jobs?.map((job) => (
            <motion.div
              key={job.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
            >
              <JobCard job={job} />
            </motion.div>
          ))}
          {jobs?.length === 0 && (
            <p className="text-sm text-muted-foreground">No open roles right now — check back soon.</p>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
}
