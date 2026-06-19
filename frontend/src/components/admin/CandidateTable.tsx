// src/components/admin/CandidateTable.tsx
"use client";

import React, { useState } from "react";
import { Users } from "lucide-react";
import type { Candidate } from "@/types";
import { formatDuration as fmtDuration, cn } from "@/lib/utils";
import { avatarGradient, initials, scoreMeta, scoreTier } from "@/lib/score";
import { Reveal } from "@/components/ui/Reveal";
import { StatusBadge } from "./StatusBadge";
import { StatusBadge as HRStatusBadge } from "../candidates/StatusBadge";
import { CandidateActions } from "../candidates/CandidateActions";
import { CandidateNotesPanel } from "../candidates/CandidateNotesPanel";

interface CandidateTableProps {
  candidates: Candidate[];
  isLoading?: boolean;
  onView: (candidate: Candidate) => void;
  onUpdate: () => void;
}

function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const days = Math.floor((Date.now() - then) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "1d ago";
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

const NOTABLE_SYSTEM = new Set(["Queued", "Processing", "Ungraded", "Error"]);

/** Score number coloring by tier thresholds. */
function scoreColor(score: number | null | undefined): string {
  const tier = scoreTier(score);
  if (tier === "strong") return "text-strong";
  if (tier === "promising") return "text-promising";
  return "text-weak";
}

/** Status pill styling for pipeline (evaluation) status. */
function pipelineStatusStyle(status: string): string {
  if (status === "Shortlisted" || status === "Processed" || status === "Reviewed")
    return "bg-strong/15 text-strong";
  if (status === "Queued" || status === "Processing" || status === "Pending")
    return "bg-promising/15 text-promising";
  if (status === "Failed" || status === "Error" || status === "Rejected")
    return "bg-weak/15 text-weak";
  return "bg-foreground/[0.07] text-muted-foreground";
}

/** Three tiny tier dots with individual tooltips. */
function TierDots({ cand }: { cand: Candidate }) {
  const dots = [
    { key: "t1", value: cand.tier1 ?? 0, max: 30, color: "var(--strong)", label: "Profile (Tier 1)" },
    { key: "t2", value: cand.tier2 ?? 0, max: 40, color: "var(--primary)", label: "Semantic (Tier 2)" },
    { key: "t3", value: cand.tier3 ?? 0, max: 30, color: "var(--promising)", label: "LLM (Tier 3)" },
  ];
  return (
    <div className="flex items-center gap-2">
      {dots.map((d) => {
        const pct = Math.round((d.value / d.max) * 100);
        return (
          <div key={d.key} className="flex flex-col items-center gap-1" title={`${d.label}: ${d.value.toFixed(1)}/${d.max} (${pct}%)`}>
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: d.color, opacity: d.value > 0 ? 1 : 0.2 }}
            />
            <span className="font-mono text-[10px] text-muted-foreground tabular-nums leading-none">
              {d.value.toFixed(0)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** Stacked progress bar showing tier breakdown proportional to /100. */
function TierBar({ cand }: { cand: Candidate }) {
  const t1 = cand.tier1 ?? 0;
  const t2 = cand.tier2 ?? 0;
  const t3 = cand.tier3 ?? 0;
  return (
    <div
      className="mt-1.5 flex h-1 w-full overflow-hidden rounded-full bg-foreground/[0.07]"
      title={`T1 ${t1.toFixed(1)} · T2 ${t2.toFixed(1)} · T3 ${t3.toFixed(1)}`}
      aria-hidden
    >
      <span className="h-full transition-[width] duration-500" style={{ width: `${t1}%`, background: "var(--strong)" }} />
      <span className="h-full transition-[width] duration-500" style={{ width: `${t2}%`, background: "var(--primary)" }} />
      <span className="h-full transition-[width] duration-500" style={{ width: `${t3}%`, background: "var(--promising)" }} />
    </div>
  );
}

const COL = "grid-cols-[2.2fr_1fr_1.1fr_1fr_1.1fr_0.8fr_auto]";

export const CandidateTable: React.FC<CandidateTableProps> = ({
  candidates,
  isLoading,
  onView,
  onUpdate,
}) => {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const toggleNotes = (id: number) =>
    setExpandedId((prev) => (prev === id ? null : id));

  return (
    <div className="overflow-hidden rounded-2xl border border-border">
      <div className="overflow-x-auto">
        <div className="min-w-[860px]">
          {/* Header */}
          <div
            className={cn(
              "grid gap-3 border-b border-border px-4 py-3",
              "bg-white/[0.03] font-mono text-[11px] uppercase tracking-widest text-muted-foreground",
              COL
            )}
          >
            <div>Candidate</div>
            <div>Score</div>
            <div>Tiers</div>
            <div>Aptitude</div>
            <div>Status</div>
            <div>Submitted</div>
            <div aria-hidden />
          </div>

          {/* Loading skeleton */}
          {isLoading ? (
            <div>
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className={cn(
                    "grid items-center gap-3 border-b border-border px-4 py-3",
                    COL
                  )}
                  style={{ opacity: 1 - i * 0.08 }}
                >
                  <div className="flex items-center gap-3">
                    <div className="h-9 w-9 shrink-0 animate-pulse rounded-full bg-foreground/[0.07]" />
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <div className="h-3 w-3/5 animate-pulse rounded bg-foreground/[0.07]" />
                      <div className="h-2.5 w-2/5 animate-pulse rounded bg-foreground/[0.05]" />
                    </div>
                  </div>
                  <div className="h-6 w-14 animate-pulse rounded bg-foreground/[0.07]" />
                  <div className="flex gap-1.5">
                    {[0,1,2].map((j) => (
                      <div key={j} className="h-2 w-2 animate-pulse rounded-full bg-foreground/[0.07]" />
                    ))}
                  </div>
                  <div className="h-4 w-12 animate-pulse rounded bg-foreground/[0.07]" />
                  <div className="h-5 w-20 animate-pulse rounded-full bg-foreground/[0.07]" />
                  <div className="h-3.5 w-10 animate-pulse rounded bg-foreground/[0.05]" />
                  <div />
                </div>
              ))}
            </div>
          ) : candidates.length === 0 ? (
            /* Empty state */
            <div className="flex flex-col items-center gap-3 px-6 py-16 text-center">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                <Users className="h-6 w-6" />
              </span>
              <p className="font-display text-base font-semibold text-heading">No candidates yet</p>
              <p className="max-w-sm text-sm text-muted-foreground">
                No candidates match the selected filters. Try clearing the search or status filters, or invite applicants to this role.
              </p>
            </div>
          ) : (
            candidates.map((cand, idx) => {
              const effective = cand.hr_score_override ?? cand.total_score;
              const overridden =
                cand.hr_score_override !== null &&
                cand.hr_score_override !== undefined;
              const name = cand.name || cand.filename;
              const subParts = [
                cand.current_role,
                cand.years_experience != null
                  ? `${cand.years_experience} yrs`
                  : null,
              ].filter(Boolean);
              const expanded = expandedId === cand.id;
              const meta = scoreMeta(effective);

              return (
                <React.Fragment key={cand.id}>
                  <Reveal
                    index={idx}
                    role="button"
                    tabIndex={0}
                    onClick={() => onView(cand)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onView(cand);
                      }
                    }}
                    className={cn(
                      "group relative grid cursor-pointer items-center gap-3 border-b border-border px-4 py-3",
                      "transition-colors duration-150 hover:bg-white/[0.02] last:border-0",
                      "focus:outline-none focus-visible:bg-white/[0.03]",
                      COL
                    )}
                  >
                    {/* Left accent rail */}
                    <span
                      aria-hidden
                      className="pointer-events-none absolute inset-y-2.5 left-0 w-[3px] origin-center scale-y-0 rounded-r-full opacity-0 transition-all duration-200 group-hover:scale-y-100 group-hover:opacity-100"
                      style={{ background: meta.colorVar }}
                    />

                    {/* Candidate */}
                    <div className="flex min-w-0 items-center gap-3">
                      <span
                        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
                        style={{ background: avatarGradient(name ?? "?") }}
                        aria-hidden
                      >
                        {initials(cand.name) === "··"
                          ? (cand.filename?.[0] ?? "?").toUpperCase()
                          : initials(cand.name)}
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-heading">
                          {name}
                        </p>
                        <p className="truncate text-xs text-muted-foreground">
                          {subParts.length
                            ? subParts.join(" · ")
                            : (cand.email ?? "No email captured")}
                        </p>
                        {NOTABLE_SYSTEM.has(cand.status) && (
                          <span className="mt-1 inline-block">
                            <StatusBadge status={cand.status} />
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Score */}
                    <div className="flex flex-col gap-0.5">
                      <div className="flex items-baseline gap-0.5">
                        <span
                          className={cn(
                            "font-mono text-lg font-bold tabular-nums leading-none",
                            scoreColor(effective)
                          )}
                        >
                          {Math.round(effective ?? 0)}
                        </span>
                        <span className="font-mono text-[11px] text-muted-foreground">
                          /100
                        </span>
                      </div>
                      {overridden && (
                        <span className="text-[9px] font-semibold uppercase tracking-wide text-promising">
                          overridden
                        </span>
                      )}
                    </div>

                    {/* Tiers */}
                    <div className="space-y-1.5">
                      <TierDots cand={cand} />
                      <TierBar cand={cand} />
                    </div>

                    {/* Aptitude */}
                    <div>
                      {cand.iq_score != null ? (
                        <>
                          <div className="font-mono text-sm text-foreground">
                            {cand.iq_total
                              ? Math.round(
                                  (cand.iq_correct! / cand.iq_total) * 100
                                )
                              : Math.round(cand.iq_score)}
                            %
                            <span className="ml-1 text-[10px] text-muted-foreground">acc</span>
                          </div>
                          <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                            {cand.iq_time_seconds != null
                              ? fmtDuration(cand.iq_time_seconds)
                              : "—"}
                          </div>
                        </>
                      ) : (
                        <span className="text-xs text-muted-foreground/50">Not taken</span>
                      )}
                    </div>

                    {/* Status */}
                    <div
                      className="flex flex-col gap-1.5"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <span
                        className={cn(
                          "inline-flex w-fit items-center rounded-full px-2.5 py-1 text-xs font-medium",
                          pipelineStatusStyle(cand.status)
                        )}
                      >
                        {cand.status}
                      </span>
                      {cand.hr_status && <HRStatusBadge status={cand.hr_status} />}
                    </div>

                    {/* Submitted */}
                    <div className="font-mono text-[12px] text-muted-foreground">
                      {timeAgo(cand.created_at)}
                    </div>

                    {/* Actions */}
                    <div
                      className="flex items-center justify-end gap-1"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex items-center gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100">
                        <CandidateActions
                          candidate={cand}
                          onUpdate={onUpdate}
                          onToggleNote={() => toggleNotes(cand.id)}
                        />
                      </div>
                      <a
                        href={`/admin/candidates/${cand.id}/interview`}
                        onClick={(e) => e.stopPropagation()}
                        className="inline-flex items-center rounded-lg border border-border px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:bg-white/5 focus:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                        title="Open interview page"
                      >
                        View
                      </a>
                    </div>
                  </Reveal>

                  {/* Expanded notes panel */}
                  {expanded && (
                    <div className="border-b border-border bg-white/[0.01] px-4 py-4">
                      <div className="glass-tile max-w-3xl rounded-xl p-4">
                        <CandidateNotesPanel
                          candidateId={cand.id}
                          hrNotes={cand.hr_notes}
                          onUpdate={onUpdate}
                          onClose={() => toggleNotes(cand.id)}
                        />
                      </div>
                    </div>
                  )}
                </React.Fragment>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
