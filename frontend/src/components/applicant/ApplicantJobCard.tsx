"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { Job } from "@/types";

interface Props {
  job: Job;
  href?: string;
  brandColor?: string;
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
