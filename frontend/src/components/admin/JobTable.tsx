// src/components/admin/JobTable.tsx
"use client";

import React from "react";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableCaption } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Edit, Trash2 } from "lucide-react";
import type { Job } from "@/types";
import { StatusBadge } from "./StatusBadge";

interface JobTableProps {
  jobs: Job[];
  isLoading?: boolean;
  onEdit: (job: Job) => void;
  onArchive: (job: Job) => void;
}

export const JobTable: React.FC<JobTableProps> = ({ jobs, isLoading, onEdit, onArchive }) => {
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
          {isLoading ? (
            // Show three skeleton rows while loading
            Array.from({ length: 3 }).map((_, i) => (
              <TableRow key={i} className="animate-pulse">
                <TableCell colSpan={5} className="h-12 bg-card/20" />
              </TableRow>
            ))
          ) : jobs.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} className="h-24 text-center text-sm text-muted-foreground">
                No active jobs yet. Create a job to start accepting candidates.
              </TableCell>
            </TableRow>
          ) : (
            jobs.map((job) => (
              <TableRow key={job.id}>
                <TableCell className="font-medium">{job.title}</TableCell>
                <TableCell>{job.department}</TableCell>
                <TableCell><StatusBadge status={job.status} /></TableCell>
                <TableCell className="text-right">
                  {new Date(job.created_at).toLocaleDateString()}
                </TableCell>
                <TableCell className="text-right space-x-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onEdit(job)}
                  >
                    <Edit className="h-4 w-4 mr-1" /> Edit
                  </Button>
                  {job.status !== "Archived" && (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => onArchive(job)}
                    >
                      <Trash2 className="h-4 w-4 mr-1" /> Archive
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
};
