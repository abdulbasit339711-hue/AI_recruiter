// src/components/admin/JobTable.tsx
"use client";

import React from "react";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableCaption } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Reveal } from "@/components/ui/Reveal";
import { Edit, Trash2, Briefcase } from "lucide-react";
import type { Job } from "@/types";
import { StatusBadge } from "./StatusBadge";

interface JobTableProps {
  jobs: Job[];
  isLoading?: boolean;
  onEdit: (job: Job) => void;
  onArchive: (job: Job) => void;
}

export const JobTable: React.FC<JobTableProps> = ({ jobs, isLoading, onEdit, onArchive }) => {
  // Animated skeleton — column-aligned shimmer blocks while loading.
  if (isLoading) {
    return (
      <div className="glass overflow-x-auto rounded-2xl">
        <Table>
          <TableHeader>
            <TableRow className="bg-card-foreground/5">
              <TableHead>Title</TableHead>
              <TableHead>Department</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Created</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Array.from({ length: 4 }).map((_, i) => (
              <TableRow key={i} className="animate-pulse">
                <TableCell><span className="block h-3.5 w-40 rounded bg-foreground/[0.08]" /></TableCell>
                <TableCell><span className="block h-3.5 w-24 rounded bg-foreground/[0.06]" /></TableCell>
                <TableCell><span className="block h-5 w-16 rounded-full bg-foreground/[0.06]" /></TableCell>
                <TableCell className="text-right"><span className="ml-auto block h-3.5 w-20 rounded bg-foreground/[0.06]" /></TableCell>
                <TableCell className="text-right"><span className="ml-auto block h-7 w-28 rounded-md bg-foreground/[0.06]" /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    );
  }

  // Tasteful empty state.
  if (jobs.length === 0) {
    return (
      <div className="glass flex flex-col items-center justify-center gap-3 rounded-2xl px-6 py-16 text-center">
        <span
          className="flex h-12 w-12 items-center justify-center rounded-2xl"
          style={{ background: "color-mix(in srgb, var(--primary) 12%, transparent)", color: "var(--primary)" }}
        >
          <Briefcase className="h-5 w-5" strokeWidth={2} />
        </span>
        <p className="text-sm font-medium text-heading">No jobs yet — create your first opening</p>
        <p className="max-w-sm text-xs text-muted-foreground">
          Add a role to start accepting candidates and running AI screening.
        </p>
      </div>
    );
  }

  return (
    <div className="glass overflow-x-auto rounded-2xl">
      <Table>
        <TableCaption>All job postings</TableCaption>
        <TableHeader>
          <TableRow className="bg-card-foreground/5">
            <TableHead>Title</TableHead>
            <TableHead>Department</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Created</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {jobs.map((job, i) => (
            <Reveal
              as="tr"
              index={i}
              key={job.id}
              className="border-b border-border transition-colors hover:bg-foreground/[0.03]"
            >
              <TableCell className="font-medium text-heading">{job.title}</TableCell>
              <TableCell className="text-muted-foreground">{job.department}</TableCell>
              <TableCell><StatusBadge status={job.status} /></TableCell>
              <TableCell className="text-right font-mono text-xs tabular-nums text-muted-foreground">
                {new Date(job.created_at).toLocaleDateString()}
              </TableCell>
              <TableCell className="space-x-2 text-right">
                <Button variant="outline" size="sm" onClick={() => onEdit(job)}>
                  <Edit className="h-4 w-4 mr-1" /> Edit
                </Button>
                {job.status !== "Archived" && (
                  <Button variant="destructive" size="sm" onClick={() => onArchive(job)}>
                    <Trash2 className="h-4 w-4 mr-1" /> Archive
                  </Button>
                )}
              </TableCell>
            </Reveal>
          ))}
        </TableBody>
      </Table>
    </div>
  );
};
