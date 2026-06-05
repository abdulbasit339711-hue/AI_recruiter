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
        <Card className="h-full transition-colors hover:border-sky-400/30">
          <CardHeader>
            <CardTitle className="text-xl font-bold">{job.title}</CardTitle>
            <CardDescription className="text-sm text-muted-foreground">
              {job.department}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="line-clamp-3 text-sm" title={job.job_description}>
              {job.job_description}
            </p>
            <span className="inline-flex items-center gap-2 text-sm font-medium text-sky-200">
              View role <ArrowRight className="h-4 w-4" />
            </span>
          </CardContent>
        </Card>
      </Link>
    </motion.div>
  );
};
