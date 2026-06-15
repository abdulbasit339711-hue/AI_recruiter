// src/components/admin/CandidateTable.tsx
"use client";

import React, { useState } from "react";
import { ChevronRight } from "lucide-react";
import type { Candidate } from "@/types";
import { formatDuration as fmtDuration, cn } from "@/lib/utils";
import { avatarGradient, initials } from "@/lib/score";
import { ScoreChip } from "@/components/ui/ScoreChip";
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

// Same column rhythm as the design spec.
const GRID = "grid-cols-[2.4fr_1.3fr_1.1fr_1.5fr_1.2fr_0.9fr_40px]";

/** Profile (Tier 1, /30) + semantic (Tier 2, /40) → a 0–100 résumé-fit number. */
function resumeMatch(c: Candidate): number {
  return Math.round((((c.tier1 ?? 0) + (c.tier2 ?? 0)) / 70) * 100);
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

// System (pipeline) states worth surfacing under the name; "Reviewed" is the steady state.
const NOTABLE_SYSTEM = new Set(["Queued", "Processing", "Ungraded", "Error"]);

export const CandidateTable: React.FC<CandidateTableProps> = ({ candidates, isLoading, onView, onUpdate }) => {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const toggleNotes = (id: number) => setExpandedId((prev) => (prev === id ? null : id));

  return (
    <div className="glass overflow-hidden rounded-2xl">
      <div className="overflow-x-auto">
        <div className="min-w-[860px]">
          {/* Header */}
          <div
            className={cn(
              "grid gap-3 border-b border-border px-[22px] py-3.5 font-mono text-[11px] uppercase tracking-[0.08em] text-faint",
              GRID
            )}
          >
            <div>Candidate</div>
            <div className="flex items-center gap-1.5 text-primary-strong">
              Match
              <ChevronRight className="h-3 w-3 rotate-90" />
            </div>
            <div>Résumé</div>
            <div>Aptitude (IQ)</div>
            <div>HR status</div>
            <div>Submitted</div>
            <div aria-hidden />
          </div>

          {/* Body */}
          {isLoading ? (
            <div className="space-y-px">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className={cn("grid gap-3 px-[22px] py-4", GRID)}>
                  <div className="loading h-10 rounded-lg" />
                  <div className="loading h-6 rounded-lg" />
                  <div className="loading h-6 rounded-lg" />
                  <div className="loading h-6 rounded-lg" />
                  <div className="loading h-6 rounded-lg" />
                  <div className="loading h-6 rounded-lg" />
                  <div />
                </div>
              ))}
            </div>
          ) : candidates.length === 0 ? (
            <div className="px-6 py-16 text-center text-sm text-muted-foreground">
              No candidates match the selected filters.
            </div>
          ) : (
            candidates.map((cand, idx) => {
              const effective = cand.hr_score_override ?? cand.total_score;
              const overridden = cand.hr_score_override !== null && cand.hr_score_override !== undefined;
              const name = cand.name || cand.filename;
              const subParts = [
                cand.current_role,
                cand.years_experience != null ? `${cand.years_experience} yrs` : null,
              ].filter(Boolean);
              const expanded = expandedId === cand.id;

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
                      "group grid cursor-pointer items-center gap-3 border-b border-border/60 px-[22px] py-4 transition-colors hover:bg-foreground/[0.03] focus:outline-none focus-visible:bg-foreground/[0.05]",
                      GRID
                    )}
                  >
                    {/* Candidate */}
                    <div className="flex min-w-0 items-center gap-3">
                      <span
                        className="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-[11px] text-[13px] font-semibold text-white"
                        style={{ background: avatarGradient(name) }}
                        aria-hidden
                      >
                        {initials(cand.name) === "··" ? (cand.filename?.[0] ?? "?").toUpperCase() : initials(cand.name)}
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-heading">{name}</p>
                        <p className="truncate text-xs text-muted-foreground">
                          {subParts.length ? subParts.join(" · ") : cand.email ?? "No email captured"}
                        </p>
                        {NOTABLE_SYSTEM.has(cand.status) && (
                          <span className="mt-1 inline-block">
                            <StatusBadge status={cand.status} />
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Match */}
                    <div className="flex items-center gap-2.5">
                      <span className="font-mono text-xl font-semibold leading-none text-heading">
                        {Math.round(effective ?? 0)}
                      </span>
                      <div className="flex flex-col items-start gap-0.5">
                        <ScoreChip score={effective} size="sm" />
                        {overridden && (
                          <span className="text-[9px] font-semibold uppercase tracking-wide text-promising">
                            Overridden
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Résumé */}
                    <div
                      className="font-mono text-[15px] text-foreground"
                      title="Profile + semantic résumé match"
                    >
                      {resumeMatch(cand)}
                    </div>

                    {/* Aptitude (IQ) */}
                    <div>
                      {cand.iq_score != null ? (
                        <>
                          <div className="font-mono text-sm text-foreground">
                            {cand.iq_total ? Math.round((cand.iq_correct! / cand.iq_total) * 100) : Math.round(cand.iq_score)}%
                            <span className="ml-1 text-xs text-faint">acc</span>
                          </div>
                          <div className="mt-0.5 font-mono text-xs text-muted-foreground">
                            {cand.iq_time_seconds != null ? fmtDuration(cand.iq_time_seconds) : "—"}
                          </div>
                        </>
                      ) : (
                        <span className="text-xs text-faint">Not taken</span>
                      )}
                    </div>

                    {/* HR status */}
                    <div onClick={(e) => e.stopPropagation()}>
                      <HRStatusBadge status={cand.hr_status} />
                    </div>

                    {/* Submitted */}
                    <div className="text-[13px] text-muted-foreground">{timeAgo(cand.created_at)}</div>

                    {/* Affordance + hover actions */}
                    <div className="flex items-center justify-end" onClick={(e) => e.stopPropagation()}>
                      <div className="hidden group-hover:flex group-focus-within:flex">
                        <CandidateActions candidate={cand} onUpdate={onUpdate} onToggleNote={() => toggleNotes(cand.id)} />
                      </div>
                      <ChevronRight className="h-[18px] w-[18px] text-faint transition-colors group-hover:text-foreground" />
                    </div>
                  </Reveal>

                  {expanded && (
                    <div className="border-b border-border/60 bg-foreground/[0.02] px-[22px] py-4">
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
