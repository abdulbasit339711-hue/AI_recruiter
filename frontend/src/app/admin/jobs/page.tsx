// src/app/admin/jobs/page.tsx
"use client"

import React, { useState } from "react"
import { useJobs } from "@/hooks/useJobs"
import { useCreateJob } from "@/hooks/useCreateJob"
import { useUpdateJob } from "@/hooks/useUpdateJob"
import { useArchiveJob } from "@/hooks/useArchiveJob"
import { JobTable } from "@/components/admin/JobTable"
import { JobFormModal } from "@/components/admin/JobFormModal"
import { Button } from "@/components/ui/button"
import { Plus } from "lucide-react"
import type { Job } from "@/types"

export default function AdminJobsPage() {
  const { data: jobs = [], isLoading, isError, error } = useJobs()
  const createJobMutation = useCreateJob()
  const updateJobMutation = useUpdateJob()
  const archiveJobMutation = useArchiveJob()

  const [isModalOpen, setModalOpen] = useState(false)
  const [editingJob, setEditingJob] = useState<Job | null>(null);
  

  const openCreate = () => {
    setEditingJob(null)
    setModalOpen(true)
  }

  const openEdit = (job: Job) => {
    setEditingJob(job)
    setModalOpen(true)
  }

  const handleSubmit = async (data: {
    title: string;
    department: string;
    job_description: string;
    llm_prompt?: string;
  }, id?: number) => {
    if (id) {
      await updateJobMutation.mutateAsync({ id, ...data })
    } else {
      await createJobMutation.mutateAsync(data)
    }
  }

  const handleArchive = async (job: Job) => {
    await archiveJobMutation.mutateAsync(job.id)
  }

  if (isLoading) {
    return <div className="rounded-md border border-white/10 bg-card/80 p-6 text-sm text-muted-foreground">Loading jobs...</div>
  }
  if (isError) {
    return (
      <div className="rounded-md border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-200">
        Error loading jobs: {error instanceof Error ? error.message : "Unknown"}
      </div>
    )
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Job Management</h1>
          <p className="mt-1 text-sm text-muted-foreground">Create roles, tune prompts, and archive closed openings.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={openCreate} variant="default" size="sm">
            <Plus className="h-4 w-4 mr-1" /> New Job
          </Button>
        </div>
      </div>
      <JobTable
        jobs={jobs}
        isLoading={isLoading}
        onEdit={openEdit}
        onArchive={handleArchive}
      />
      <JobFormModal
        open={isModalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleSubmit}
        initialData={editingJob ?? undefined}
      />
    </section>
  )
}
