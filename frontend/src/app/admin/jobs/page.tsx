// src/app/admin/jobs/page.tsx
"use client"

import React, { useState } from "react"
import { useJobs } from "@/hooks/useJobs"
import { useCreateJob } from "@/hooks/useCreateJob"
import { useUpdateJob } from "@/hooks/useUpdateJob"
import { useArchiveJob } from "@/hooks/useArchiveJob"
import { JobCard } from "@/components/job/JobCard"
import { JobFormModal } from "@/components/admin/JobFormModal"
import { Button } from "@/components/ui/button"
import { FadeIn, Stagger, StaggerItem } from "@/components/ui/motion"
import { Plus, Briefcase } from "lucide-react"
import type { Job } from "@/types"

export default function AdminJobsPage() {
  const { data: jobs = [], isLoading, isError, error } = useJobs()
  const createJobMutation = useCreateJob()
  const updateJobMutation = useUpdateJob()
  const archiveJobMutation = useArchiveJob()

  const [isModalOpen, setModalOpen] = useState(false)
  const [editingJob, setEditingJob] = useState<Job | null>(null)

  const openCreate = () => {
    setEditingJob(null)
    setModalOpen(true)
  }

  const openEdit = (job: Job) => {
    setEditingJob(job)
    setModalOpen(true)
  }

  const handleSubmit = async (
    data: {
      title: string
      department: string
      job_description: string
      llm_prompt?: string
    },
    id?: number
  ) => {
    if (id) {
      await updateJobMutation.mutateAsync({ id, ...data })
    } else {
      await createJobMutation.mutateAsync(data)
    }
  }

  const handleArchive = async (job: Job) => {
    await archiveJobMutation.mutateAsync(job.id)
  }

  if (isError) {
    return (
      <div className="rounded-xl border border-weak/20 bg-weak/10 p-4 text-sm text-weak">
        Error loading jobs: {error instanceof Error ? error.message : "Unknown"}
      </div>
    )
  }

  return (
    <section className="space-y-6">
      {/* Header */}
      <FadeIn
        as="header"
        className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"
      >
        <div className="flex flex-col gap-1">
          <p className="font-mono text-xs uppercase tracking-[0.06em] text-muted-foreground">
            Jobs
          </p>
          <h1 className="font-display text-[30px] font-bold leading-none tracking-tight text-heading">
            Jobs
          </h1>
          <p className="text-sm text-muted-foreground">
            Create roles, tune prompts, and archive closed openings.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={openCreate} variant="default" size="sm">
            <Plus className="mr-1 h-4 w-4" />
            Create Job
          </Button>
        </div>
      </FadeIn>

      {/* Loading skeletons */}
      {isLoading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="glass-tile animate-pulse rounded-2xl p-5"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="h-4 w-40 rounded bg-foreground/[0.08]" />
                <div className="h-5 w-16 rounded-full bg-foreground/[0.06]" />
              </div>
              <div className="mt-2 h-3 w-24 rounded bg-foreground/[0.06]" />
              <div className="my-3 border-t border-border" />
              <div className="flex gap-6">
                <div className="h-8 w-10 rounded bg-foreground/[0.08]" />
                <div className="h-8 w-24 rounded bg-foreground/[0.06]" />
              </div>
              <div className="my-3 border-t border-border" />
              <div className="flex gap-2">
                <div className="h-7 w-28 rounded-lg bg-foreground/[0.08]" />
                <div className="h-7 w-14 rounded-lg bg-foreground/[0.06]" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && jobs.length === 0 && (
        <FadeIn delay={0.08}>
          <div className="glass flex flex-col items-center justify-center gap-4 rounded-2xl px-6 py-20 text-center">
            <span
              className="flex h-14 w-14 items-center justify-center rounded-2xl"
              style={{
                background: "color-mix(in srgb, var(--primary) 12%, transparent)",
                color: "var(--primary)",
              }}
            >
              <Briefcase className="h-6 w-6" strokeWidth={2} />
            </span>
            <div className="flex flex-col gap-1.5">
              <p className="text-sm font-semibold text-heading">
                No jobs yet — create your first opening
              </p>
              <p className="max-w-xs text-xs text-muted-foreground">
                Add a role to start accepting candidates and running AI screening.
              </p>
            </div>
            <Button onClick={openCreate} variant="default" size="sm">
              <Plus className="mr-1 h-4 w-4" />
              Create Job
            </Button>
          </div>
        </FadeIn>
      )}

      {/* Jobs grid */}
      {!isLoading && jobs.length > 0 && (
        <Stagger
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
          delay={0.06}
        >
          {jobs.map((job) => (
            <StaggerItem key={job.id}>
              <JobCard
                job={job}
                onEdit={openEdit}
                onArchive={handleArchive}
              />
            </StaggerItem>
          ))}
        </Stagger>
      )}

      <JobFormModal
        open={isModalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleSubmit}
        initialData={editingJob ?? undefined}
      />
    </section>
  )
}
