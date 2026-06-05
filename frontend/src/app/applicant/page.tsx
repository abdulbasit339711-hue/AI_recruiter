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
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 p-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <motion.div
            key={i}
            className="h-48 bg-card/30 rounded-lg animate-pulse"
          />
        ))}
      </section>
    );
  }

  if (isError) {
    return (
      <div className="p-4 text-center text-red-500">
        Failed to load jobs: {error instanceof Error ? error.message : "Unknown error"}
      </div>
    );
  }

  return (
    <section className="mx-auto max-w-6xl space-y-6 p-4 py-8">
      <div>
        <h1 className="text-3xl font-semibold">Available Job Openings</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Choose a role and submit a searchable PDF resume for review.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
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
        </AnimatePresence>
      </div>
    </section>
  );
}
