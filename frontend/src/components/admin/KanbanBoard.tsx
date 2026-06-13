"use client";

import React, { useState } from "react";
import type { Candidate } from "@/types";
import { formatDuration } from "@/lib/utils";
import { ScoreBar } from "./ScoreBar";
import { Button } from "@/components/ui/button";
import { Eye, FileText, MessageSquare } from "lucide-react";
import { StatusBadge } from "./StatusBadge";
import { CandidateActions } from "../candidates/CandidateActions";
import { CandidateNotesPanel } from "../candidates/CandidateNotesPanel";
import { motion, AnimatePresence } from "framer-motion";

interface KanbanBoardProps {
  candidates: Candidate[];
  onView: (candidate: Candidate) => void;
  onUpdate: () => void;
}

const COLUMNS = ["Applied", "Screened", "Interview", "Offer", "Hired", "Rejected"] as const;
type HRStatus = typeof COLUMNS[number];

const COLUMN_COLORS: Record<HRStatus, string> = {
  Applied: "border-t-gray-500",
  Screened: "border-t-blue-500",
  Interview: "border-t-purple-500",
  Offer: "border-t-yellow-500",
  Hired: "border-t-emerald-500",
  Rejected: "border-t-rose-500",
};

const COLUMN_BG_BADGES: Record<HRStatus, string> = {
  Applied: "bg-gray-500/10 text-gray-400 border-gray-500/20",
  Screened: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  Interview: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  Offer: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  Hired: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  Rejected: "bg-rose-500/10 text-rose-400 border-rose-500/20",
};

export const KanbanBoard: React.FC<KanbanBoardProps> = ({
  candidates,
  onView,
  onUpdate,
}) => {
  const [expandedCardId, setExpandedCardId] = useState<number | null>(null);

  const toggleNotes = (id: number) => {
    setExpandedCardId((prev) => (prev === id ? null : id));
  };

  // Group candidates
  const grouped = COLUMNS.reduce((acc, col) => {
    acc[col] = [];
    return acc;
  }, {} as Record<HRStatus, Candidate[]>);

  candidates.forEach((cand) => {
    const status = (cand.hr_status || "Applied") as HRStatus;
    if (grouped[status]) {
      grouped[status].push(cand);
    } else {
      grouped["Applied"].push(cand);
    }
  });

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 overflow-x-auto pb-4">
      {COLUMNS.map((col) => {
        const list = grouped[col];

        return (
          <div
            key={col}
            className={`flex flex-col rounded-lg border border-white/10 bg-card/40 p-3 min-w-[240px] border-t-4 ${COLUMN_COLORS[col]}`}
          >
            {/* Column Header */}
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-white/5">
              <span className="text-sm font-bold text-white">{col}</span>
              <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${COLUMN_BG_BADGES[col]}`}>
                {list.length}
              </span>
            </div>

            {/* Cards List */}
            <div className="flex-1 space-y-3 min-h-[500px] overflow-y-auto max-h-[70vh] pr-1">
              <AnimatePresence>
                {list.length === 0 ? (
                  <div className="flex h-32 items-center justify-center rounded-md border border-dashed border-white/5 text-xs text-muted-foreground italic">
                    No candidates
                  </div>
                ) : (
                  list.map((cand) => {
                    const isOverridden = cand.hr_score_override !== null && cand.hr_score_override !== undefined;
                    const displayScore = isOverridden ? cand.hr_score_override : cand.total_score;

                    return (
                      <motion.div
                        key={cand.id}
                        layout
                        initial={{ opacity: 0, y: 12 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        transition={{ duration: 0.2 }}
                        className="rounded-lg border border-white/5 bg-white/[0.02] p-3 space-y-3 hover:border-white/15 hover:bg-white/[0.04] transition-all duration-200"
                      >
                        {/* Name and Email */}
                        <div className="space-y-0.5">
                          <h4 className="text-xs font-bold text-white truncate" title={cand.name || cand.filename}>
                            {cand.name || cand.filename}
                          </h4>
                          <p className="text-[10px] text-muted-foreground truncate" title={cand.email || ""}>
                            {cand.email || "No email captured"}
                          </p>
                        </div>

                        {/* Effective Score */}
                        <div className="space-y-1">
                          <div className="flex items-center justify-between text-[10px]">
                            <span className="text-muted-foreground">Effective Score</span>
                            <span className={`font-semibold ${isOverridden ? "text-amber-400" : "text-emerald-400"}`}>
                              {displayScore?.toFixed(1)}
                            </span>
                          </div>
                          <ScoreBar value={displayScore} />
                          {isOverridden && (
                            <p className="text-[9px] text-amber-500 font-medium">
                              Overridden (Original: {cand.total_score.toFixed(1)})
                            </p>
                          )}
                          {cand.iq_score != null && (
                            <p className="text-[9px] text-muted-foreground">
                              IQ {Math.round(cand.iq_score)}%
                              {cand.iq_total ? ` · ${cand.iq_correct}/${cand.iq_total}` : ""}
                              {cand.iq_time_seconds != null ? ` · ${formatDuration(cand.iq_time_seconds)}` : ""}
                            </p>
                          )}
                        </div>

                        {/* System Status badge & Submitted Date */}
                        <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                          <StatusBadge status={cand.status} />
                          <span>{new Date(cand.created_at).toLocaleDateString()}</span>
                        </div>

                        {/* Actions wrapper */}
                        <div className="border-t border-white/5 pt-2 flex flex-col gap-2">
                          <div className="flex items-center justify-between gap-1">
                            <CandidateActions
                              candidate={cand}
                              onUpdate={onUpdate}
                              onToggleNote={() => toggleNotes(cand.id)}
                            />
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-8 w-8 p-0"
                              onClick={() => onView(cand)}
                              title="View full profile"
                            >
                              <Eye className="h-3.5 w-3.5" />
                            </Button>
                          </div>

                          {/* Expanded Notes Section inside Kanban card */}
                          {expandedCardId === cand.id && (
                            <div className="mt-2 rounded border border-white/10 bg-black/60 p-2.5">
                              <CandidateNotesPanel
                                candidateId={cand.id}
                                hrNotes={cand.hr_notes}
                                onUpdate={onUpdate}
                                onClose={() => toggleNotes(cand.id)}
                              />
                            </div>
                          )}
                        </div>
                      </motion.div>
                    );
                  })
                )}
              </AnimatePresence>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default KanbanBoard;
