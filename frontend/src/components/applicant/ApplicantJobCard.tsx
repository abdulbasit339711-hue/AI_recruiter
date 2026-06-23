"use client";

import Link from "next/link";
import { ArrowRight, Clock } from "lucide-react";
import type { Job } from "@/types";

interface Props {
  job: Job;
  href?: string;
  brandColor?: string;
}

function deadlineLabel(iso: string | null | undefined): { text: string; color: string } | null {
  if (!iso) return null;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const d = new Date(iso);
  const diff = Math.ceil((d.getTime() - today.getTime()) / 86_400_000);
  const fmt = (dt: Date) => dt.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  if (diff < 0)  return { text: `Closed ${fmt(d)}`,           color: "#9ca3af" };
  if (diff === 0) return { text: "Closes today",               color: "#f59e0b" };
  if (diff <= 7)  return { text: `Closes ${fmt(d)} · ${diff}d left`, color: "#f59e0b" };
  return           { text: `Apply by ${fmt(d)}`,               color: "#6b7280" };
}

export function ApplicantJobCard({ job, href, brandColor }: Props) {
  const color = brandColor || process.env.NEXT_PUBLIC_ORG_COLOR || "#1C99BF";
  const dest = href || `/applicant/${job.id}`;
  const snippet = (job.job_description ?? "").slice(0, 140).trimEnd();

  return (
    <Link
      href={dest}
      className="group flex flex-col gap-4 rounded-2xl border p-6 transition-all duration-200 hover:-translate-y-0.5"
      style={{
        background: "var(--surface-card)",
        borderColor: "var(--surface-border)",
        backdropFilter: "blur(12px)",
      }}
    >
      <span
        className="self-start rounded-full px-2.5 py-0.5 text-xs font-medium"
        style={{
          background: `${color}18`,
          color,
          border: `1px solid ${color}30`,
        }}
      >
        {job.department}
      </span>

      <h2 className="text-lg font-semibold leading-snug text-heading group-hover:text-primary transition-colors">
        {job.title}
      </h2>

      {snippet && (
        <p className="flex-1 text-sm leading-relaxed text-muted-foreground line-clamp-3">
          {snippet}{snippet.length < (job.job_description ?? "").length ? "…" : ""}
        </p>
      )}

      {(() => {
        const dl = deadlineLabel(job.resume_deadline);
        if (!dl) return null;
        return (
          <span className="flex items-center gap-1 text-xs" style={{ color: dl.color }}>
            <Clock className="h-3 w-3 shrink-0" />
            {dl.text}
          </span>
        );
      })()}

      <div
        className="mt-auto flex items-center gap-1.5 text-sm font-semibold"
        style={{ color }}
      >
        View & apply
        <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
      </div>
    </Link>
  );
}
