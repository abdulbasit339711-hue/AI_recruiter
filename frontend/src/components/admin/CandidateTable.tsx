// src/components/admin/CandidateTable.tsx
"use client";

import React, { useState } from "react";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableCaption } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Eye } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import type { Candidate } from "@/types";
import { formatDuration as fmtDuration } from "@/lib/utils";
import { ScoreBar } from "./ScoreBar";
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

export const CandidateTable: React.FC<CandidateTableProps> = ({ candidates, isLoading, onView, onUpdate }) => {
  const [expandedCandidateId, setExpandedCandidateId] = useState<number | null>(null);

  const toggleNotes = (id: number) => {
    setExpandedCandidateId((prev) => (prev === id ? null : id));
  };

  const rowVariants = {
    hidden: { opacity: 0, y: 10 },
    visible: { opacity: 1, y: 0 },
  };

  return (
    <div className="overflow-x-auto rounded-md border border-white/10 bg-card/80">
      <Table>
        <TableCaption>Candidate leaderboard for the selected job</TableCaption>
        <TableHeader>
          <TableRow className="bg-white/[0.03]">
            <TableHead>Name / Email</TableHead>
            <TableHead>Effective Score</TableHead>
            <TableHead>Tier Scores</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>HR Status</TableHead>
            <TableHead className="text-right">Submitted</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow className="animate-pulse">
              <TableCell colSpan={7} className="h-16 bg-white/[0.03]" />
            </TableRow>
          ) : candidates.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="h-24 text-center text-sm text-muted-foreground">
                No candidates match the selected filters.
              </TableCell>
            </TableRow>
          ) : (
            <AnimatePresence>
              {candidates.map((cand) => (
                <React.Fragment key={cand.id}>
                  <motion.tr
                    variants={rowVariants}
                    initial="hidden"
                    animate="visible"
                    exit="hidden"
                    transition={{ duration: 0.2 }}
                    className="border-b border-white/5"
                  >
                    <TableCell className="font-medium">
                      <div className="max-w-64">
                        <p className="truncate">{cand.name || cand.filename}</p>
                        <p className="truncate text-sm text-muted-foreground">{cand.email ?? "No email captured"}</p>
                      </div>
                    </TableCell>
                    <TableCell>
                      {cand.hr_score_override !== null && cand.hr_score_override !== undefined ? (
                        <div className="flex flex-col gap-0.5">
                          <div className="flex items-center gap-1.5">
                            <ScoreBar value={cand.hr_score_override} />
                            <span className="text-[9px] font-semibold text-amber-400 bg-amber-400/10 px-1 py-0.5 rounded border border-amber-400/20 shrink-0">
                              Overridden
                            </span>
                          </div>
                          <span className="text-[10px] text-muted-foreground">
                            Original: {cand.total_score.toFixed(1)}
                          </span>
                        </div>
                      ) : (
                        <ScoreBar value={cand.total_score} />
                      )}
                    </TableCell>
                    <TableCell>
                      <span className="text-xs text-muted-foreground">
                        T1 {cand.tier1?.toFixed(1) ?? "0.0"} / T2 {cand.tier2?.toFixed(1) ?? "0.0"} / T3 {cand.tier3?.toFixed(1) ?? "0.0"}
                      </span>
                      {cand.iq_score !== null && cand.iq_score !== undefined && (
                        <span className="mt-0.5 block text-[10px] text-muted-foreground">
                          IQ {Math.round(cand.iq_score)}%
                          {cand.iq_total ? ` · ${cand.iq_correct}/${cand.iq_total}` : ""}
                          {cand.iq_time_seconds != null ? ` · ${fmtDuration(cand.iq_time_seconds)}` : ""}
                        </span>
                      )}
                    </TableCell>
                    <TableCell><StatusBadge status={cand.status} /></TableCell>
                    <TableCell><HRStatusBadge status={cand.hr_status} /></TableCell>
                    <TableCell className="text-right">{new Date(cand.created_at).toLocaleDateString()}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <CandidateActions
                          candidate={cand}
                          onUpdate={onUpdate}
                          onToggleNote={() => toggleNotes(cand.id)}
                        />
                        <Button variant="outline" size="sm" className="h-8" onClick={() => onView(cand)} title="View full details">
                          <Eye className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </motion.tr>

                  {/* Expanded Notes Section */}
                  {expandedCandidateId === cand.id && (
                    <TableRow className="border-b border-white/5 bg-white/[0.01]">
                      <TableCell colSpan={7} className="p-4 pl-8">
                        <div className="max-w-3xl rounded-md border border-white/10 bg-black/40 p-4">
                          <CandidateNotesPanel
                            candidateId={cand.id}
                            hrNotes={cand.hr_notes}
                            onUpdate={onUpdate}
                            onClose={() => toggleNotes(cand.id)}
                          />
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </React.Fragment>
              ))}
            </AnimatePresence>
          )}
        </TableBody>
      </Table>
    </div>
  );
};
