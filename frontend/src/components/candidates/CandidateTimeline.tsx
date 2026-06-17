"use client";

import React, { useEffect, useState } from "react";
import { X, Calendar, User, FileText, CheckCircle2, ShieldAlert } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { api } from "@/lib/api";
import { Stagger, StaggerItem } from "@/components/ui/motion";
import type { TimelineEntry } from "@/types";

interface CandidateTimelineProps {
  candidateId: number | null;
  candidateName: string;
  isOpen: boolean;
  onClose: () => void;
}

export const CandidateTimeline: React.FC<CandidateTimelineProps> = ({
  candidateId,
  candidateName,
  isOpen,
  onClose,
}) => {
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !candidateId) return;

    const fetchTimeline = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.getCandidateTimeline(candidateId);
        setTimeline(res.timeline);
      } catch (err) {
        setError("Failed to fetch activity history.");
      } finally {
        setLoading(false);
      }
    };

    fetchTimeline();
  }, [candidateId, isOpen]);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.5 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
          />

          {/* Drawer Container */}
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-border bg-card p-6 text-foreground shadow-2xl sm:max-w-lg"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border pb-4">
              <div>
                <h2 className="text-xl font-bold">Activity History</h2>
                <p className="text-sm text-muted-foreground">Timeline for {candidateName}</p>
              </div>
              <button
                onClick={onClose}
                className="rounded-md p-1.5 text-muted-foreground hover:bg-foreground/10 hover:text-foreground transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto py-6 pr-2">
              {loading ? (
                <div className="flex h-full items-center justify-center">
                  <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                </div>
              ) : error ? (
                <div className="flex h-full items-center justify-center text-sm text-weak">
                  {error}
                </div>
              ) : timeline.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center text-muted-foreground">
                  <Calendar className="mb-2 h-10 w-10 opacity-50" />
                  <p className="text-sm">No activity recorded yet.</p>
                </div>
              ) : (
                <Stagger gap={0.07} className="relative ml-4 space-y-8 border-l-2 border-border pl-6">
                  {timeline.map((entry, idx) => {
                    const isScoreOverride = entry.type === "score_override";
                    const Icon = isScoreOverride ? ShieldAlert : CheckCircle2;
                    const dateStr = new Date(entry.changed_at).toLocaleString();
                    const accent = isScoreOverride ? "var(--promising)" : "var(--strong)";

                    return (
                      <StaggerItem key={idx} className="relative">
                        {/* Timeline point */}
                        <div
                          className="absolute -left-[35px] top-1.5 flex h-6 w-6 items-center justify-center rounded-full border bg-card"
                          style={{ borderColor: accent, color: accent }}
                        >
                          <Icon className="h-3.5 w-3.5" />
                        </div>

                        {/* Card Content */}
                        <div className="space-y-2 rounded-lg glass-tile p-4">
                          <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                            <span className="text-sm font-semibold" style={{ color: accent }}>
                              {isScoreOverride ? "Score override" : `Status: ${entry.status}`}
                            </span>
                            <span className="font-mono text-xs tabular-nums text-muted-foreground">{dateStr}</span>
                          </div>

                          <div className="flex items-center gap-1.5 text-xs text-foreground">
                            <User className="h-3 w-3 text-muted-foreground" />
                            <span>Changed by: {entry.changed_by}</span>
                          </div>

                          {entry.note && (
                            <div className="flex items-start gap-2 rounded border border-border bg-foreground/[0.04] p-2.5 text-sm text-foreground">
                              <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                              <p className="whitespace-pre-wrap leading-relaxed">{entry.note}</p>
                            </div>
                          )}
                        </div>
                      </StaggerItem>
                    );
                  })}
                </Stagger>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default CandidateTimeline;
