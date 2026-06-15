// src/components/job/JobCard.tsx
"use client";
import React from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Job } from "@/types";

interface JobCardProps {
  job: Job;
}

export const JobCard: React.FC<JobCardProps> = ({ job }) => {
  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      className="cursor-pointer"
    >
      <Link href={`/applicant/${job.id}`}>
        <Card className="glass-hover h-full">
          <CardHeader>
            <CardDescription className="font-mono text-xs uppercase tracking-[0.06em] text-muted-foreground">
              {job.department}
            </CardDescription>
            <CardTitle className="font-display text-xl font-bold text-heading">{job.title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="line-clamp-3 text-sm text-muted-foreground" title={job.job_description}>
              {job.job_description}
            </p>
            <span className="inline-flex items-center gap-2 text-sm font-semibold text-primary-strong">
              View role <ArrowRight className="h-4 w-4" />
            </span>
          </CardContent>
        </Card>
      </Link>
    </motion.div>
  );
};
