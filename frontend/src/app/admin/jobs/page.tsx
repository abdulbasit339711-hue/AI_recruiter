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
import { GlassCard } from "@/components/ui/GlassCard"
import { FadeIn } from "@/components/ui/motion"
import { CountUp } from "@/components/ui/charts"
import { Plus, Briefcase, CheckCircle2, Archive } from "lucide-react"
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

  if (isError) {
    return (
      <div className="rounded-md border border-[var(--weak-text)]/20 bg-[var(--weak-bg)] p-4 text-sm text-[var(--weak-text)]">
        Error loading jobs: {error instanceof Error ? error.message : "Unknown"}
      </div>
    )
  }

  const activeCount = jobs.filter((j) => j.status === "Active").length
  const archivedCount = jobs.filter((j) => j.status === "Archived").length
  const stats = [
    { label: "Total jobs", value: jobs.length, icon: Briefcase, accent: "var(--primary)" },
    { label: "Active", value: activeCount, icon: CheckCircle2, accent: "var(--strong)" },
    { label: "Archived", value: archivedCount, icon: Archive, accent: "var(--muted-foreground)" },
  ]

  return (
    <section className="space-y-6">
      <FadeIn as="header" className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-col gap-1.5">
          <p className="font-mono text-xs uppercase tracking-[0.06em] text-muted-foreground">Jobs</p>
          <h1 className="font-display text-[30px] font-bold leading-none tracking-tight text-heading">Job management</h1>
          <p className="text-sm text-muted-foreground">Create roles, tune prompts, and archive closed openings.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={openCreate} variant="default" size="sm">
            <Plus className="h-4 w-4 mr-1" /> New job
          </Button>
        </div>
      </FadeIn>

      {!isLoading && jobs.length > 0 && (
        <FadeIn delay={0.08} className="grid grid-cols-3 gap-3.5">
          {stats.map((s) => (
            <GlassCard key={s.label} variant="tile" hover className="relative overflow-hidden p-4">
              <div
                aria-hidden
                className="pointer-events-none absolute -right-6 -top-8 h-20 w-20 rounded-full blur-2xl"
                style={{ background: `color-mix(in srgb, ${s.accent} 30%, transparent)` }}
              />
              <span
                className="relative flex h-9 w-9 items-center justify-center rounded-xl"
                style={{ background: `color-mix(in srgb, ${s.accent} 15%, transparent)`, color: s.accent }}
              >
                <s.icon className="h-[18px] w-[18px]" strokeWidth={2} />
              </span>
              <p className="relative mt-3 font-mono text-[26px] font-semibold leading-none tabular-nums text-heading">
                <CountUp value={s.value} />
              </p>
              <p className="relative mt-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">{s.label}</p>
            </GlassCard>
          ))}
        </FadeIn>
      )}

      <FadeIn delay={0.16}>
        <JobTable
          jobs={jobs}
          isLoading={isLoading}
          onEdit={openEdit}
          onArchive={handleArchive}
        />
      </FadeIn>
      <JobFormModal
        open={isModalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleSubmit}
        initialData={editingJob ?? undefined}
      />
    </section>
  )
}
