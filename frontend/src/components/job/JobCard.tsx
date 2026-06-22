"use client";

import React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Briefcase, Users, Archive, Edit, Calendar, Star, TrendingUp } from "lucide-react";
import type { Job } from "@/types";

interface JobCardProps {
  job: Job;
  candidateCount?: number;
  onEdit?: (job: Job) => void;
  onArchive?: (job: Job) => void;
  index?: number;
}

function scoreColor(s: number): string {
  if (s >= 70) return "#34C28A";
  if (s >= 40) return "#F5B544";
  return "#F25C7C";
}

function deadlineBadge(date: string | null | undefined): { text: string; color: string } | null {
  if (!date) return null;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const d = new Date(date);
  const diff = Math.ceil((d.getTime() - today.getTime()) / 86_400_000);
  if (diff < 0)  return { text: "Closed",              color: "#6B7280" };
  if (diff === 0) return { text: "Closes today",        color: "#EF4444" };
  if (diff <= 3)  return { text: `${diff}d left`,       color: "#EF4444" };
  if (diff <= 7)  return { text: `${diff}d left`,       color: "#F5B544" };
  return null;
}

const EASE = [0.22, 1, 0.36, 1] as const;

export const JobCard: React.FC<JobCardProps> = ({ job, candidateCount, onEdit, onArchive, index = 0 }) => {
  const count       = candidateCount ?? job.candidate_count ?? 0;
  const shortlisted = job.shortlisted_count ?? 0;
  const avgScore    = job.avg_score;
  const topScore    = job.top_score;
  const pct         = count > 0 ? Math.round((shortlisted / count) * 100) : 0;
  const resumeBadge = deadlineBadge(job.resume_deadline);
  const intBadge    = deadlineBadge(job.interview_deadline);
  const isActive    = job.status === "Active";
  const snippet     = (job.job_description ?? "").slice(0, 120);

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.05, ease: EASE }}
      className="group relative flex flex-col overflow-hidden rounded-2xl transition-all duration-200"
      style={{
        background: "var(--surface-card)",
        border: "1px solid var(--surface-border)",
      }}
    >
      {/* Hover border glow */}
      <div
        className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-200 group-hover:opacity-100"
        style={{ boxShadow: "inset 0 0 0 1px rgba(28,153,191,0.3)" }}
      />

      {/* Glow orb */}
      <div
        className="pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-20"
        style={{ background: "#1C99BF" }}
      />

      <div className="flex flex-1 flex-col p-5">
        {/* Top row: icon + status + avg score */}
        <div className="mb-3 flex items-start justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <div
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
              style={{ background: "rgba(28,153,191,0.12)", color: "#1C99BF" }}
            >
              <Briefcase className="h-4.5 w-4.5" strokeWidth={2} />
            </div>
            <div>
              <h3 className="text-sm font-semibold leading-snug text-heading line-clamp-1">
                {job.title}
              </h3>
              {job.department && (
                <span className="inline-block rounded-full px-2 py-0.5 text-[10px] font-medium mt-0.5"
                  style={{ background: "rgba(255,255,255,0.05)", color: "var(--muted-foreground)" }}>
                  {job.department}
                </span>
              )}
            </div>
          </div>

          {/* Status + avg score badge */}
          <div className="flex shrink-0 flex-col items-end gap-1">
            <span
              className="rounded-full px-2 py-0.5 text-[10px] font-medium leading-none"
              style={isActive
                ? { background: "rgba(28,153,191,0.15)", color: "#1C99BF", border: "1px solid rgba(28,153,191,0.3)" }
                : { background: "rgba(85,96,112,0.15)", color: "#6B7280", border: "1px solid rgba(85,96,112,0.25)" }}
            >
              {job.status}
            </span>
            {avgScore != null && (
              <span className="font-mono text-[10px] font-bold tabular-nums" style={{ color: scoreColor(avgScore) }}>
                avg {avgScore.toFixed(1)}
              </span>
            )}
          </div>
        </div>

        {/* Description snippet */}
        {snippet && (
          <p className="mb-3 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground/60">
            {snippet}
          </p>
        )}

        {/* Candidate pipeline bar */}
        <div className="mb-3">
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5">
              <Users className="h-3 w-3 text-muted-foreground" />
              <span className="text-[11px] text-muted-foreground">
                <span className="font-semibold text-heading">{count}</span> candidate{count !== 1 ? "s" : ""}
              </span>
            </div>
            {shortlisted > 0 && (
              <div className="flex items-center gap-1">
                <Star className="h-2.5 w-2.5 text-[#34C28A]" />
                <span className="font-mono text-[10px] font-semibold text-[#34C28A]">
                  {shortlisted} shortlisted ({pct}%)
                </span>
              </div>
            )}
          </div>
          {/* Progress bar */}
          <div className="h-1.5 w-full overflow-hidden rounded-full" style={{ background: "var(--surface-subtle, rgba(255,255,255,0.05))" }}>
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: count > 0 ? `${pct}%` : "0%" }}
              transition={{ duration: 0.9, delay: index * 0.05 + 0.2, ease: EASE }}
              className="h-full rounded-full"
              style={{
                background: pct >= 50 ? "linear-gradient(90deg, #34C28A, #4ADBA2)" :
                             pct >= 20 ? "linear-gradient(90deg, #F5B544, #FCC55E)" :
                                         "linear-gradient(90deg, #1C99BF, #3DAFCC)",
                boxShadow: `0 0 8px ${pct >= 50 ? "#34C28A" : pct >= 20 ? "#F5B544" : "#1C99BF"}40`,
              }}
            />
          </div>
        </div>

        {/* Top score + deadline badges */}
        <div className="flex flex-wrap items-center gap-1.5">
          {topScore != null && (
            <span className="flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium"
              style={{ background: `${scoreColor(topScore)}15`, color: scoreColor(topScore), border: `1px solid ${scoreColor(topScore)}25` }}>
              <TrendingUp className="h-2.5 w-2.5" />
              Top {topScore.toFixed(1)}
            </span>
          )}
          {resumeBadge && (
            <span className="flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium"
              style={{ background: `${resumeBadge.color}15`, color: resumeBadge.color }}>
              <Calendar className="h-2.5 w-2.5" />
              Resume {resumeBadge.text}
            </span>
          )}
          {intBadge && (
            <span className="flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium"
              style={{ background: `${intBadge.color}15`, color: intBadge.color }}>
              <Calendar className="h-2.5 w-2.5" />
              Interview {intBadge.text}
            </span>
          )}
        </div>
      </div>

      {/* Bottom action strip */}
      <div
        className="flex items-center gap-2 border-t px-4 py-2.5"
        style={{ borderColor: "var(--surface-border)" }}
      >
        <Link
          href={`/admin/candidates?job=${job.id}`}
          className="flex-1 rounded-lg py-1.5 text-center text-xs font-medium text-muted-foreground transition-all hover:bg-[#1C99BF]/10 hover:text-[#1C99BF]"
        >
          View candidates
        </Link>

        {onEdit && (
          <button type="button" onClick={() => onEdit(job)} title="Edit job"
            className="rounded-lg p-1.5 text-muted-foreground transition-all hover:bg-[#1C99BF]/10 hover:text-[#1C99BF]">
            <Edit className="h-3.5 w-3.5" />
          </button>
        )}

        {onArchive && job.status !== "Archived" && (
          <button type="button" onClick={() => onArchive(job)} title="Archive job"
            className="rounded-lg p-1.5 text-muted-foreground transition-all hover:bg-[#F25C7C]/10 hover:text-[#F25C7C]">
            <Archive className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </motion.div>
  );
};
