"use client";

import React, { useState } from "react";
import { MessageSquare, ShieldAlert, History, ChevronDown } from "lucide-react";
import { api } from "@/lib/api";
import { getHrActor } from "@/lib/actor";
import { toast } from "react-hot-toast";
import type { Candidate, StatusUpdatePayload, ScoreOverridePayload } from "@/types";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogClose } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CandidateTimeline } from "./CandidateTimeline";

interface CandidateActionsProps {
  candidate: Candidate;
  onUpdate: () => void;
  onToggleNote?: () => void;
}

const HR_STATUSES = ["Applied", "Screened", "Interview", "Offer", "Hired", "Rejected"] as const;

export const CandidateActions: React.FC<CandidateActionsProps> = ({
  candidate,
  onUpdate,
  onToggleNote,
}) => {
  const [statusLoading, setStatusLoading] = useState(false);
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [overrideScore, setOverrideScore] = useState<string>("");
  const [overrideReason, setOverrideReason] = useState<string>("");
  const [overrideLoading, setOverrideLoading] = useState(false);
  const [timelineOpen, setTimelineOpen] = useState(false);

  const handleStatusChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newStatus = e.target.value as typeof HR_STATUSES[number];
    if (!newStatus) return;

    setStatusLoading(true);
    try {
      await api.updateCandidateStatus(candidate.id, {
        hr_status: newStatus,
        changed_by: getHrActor(),
        note: `Status updated to ${newStatus}`,
      });
      toast.success(`Status updated to ${newStatus}`);
      onUpdate();
    } catch (err) {
      toast.error("Failed to update status.");
    } finally {
      setStatusLoading(false);
    }
  };

  const handleOverrideSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const scoreVal = parseFloat(overrideScore);

    if (isNaN(scoreVal) || scoreVal < 0 || scoreVal > 100) {
      toast.error("Please enter a valid score between 0 and 100.");
      return;
    }
    if (!overrideReason.trim()) {
      toast.error("Please provide a reason for the score override.");
      return;
    }

    setOverrideLoading(true);
    try {
      await api.overrideCandidateScore(candidate.id, {
        override_score: scoreVal,
        reason: overrideReason.trim(),
        changed_by: getHrActor(),
      });
      toast.success("Candidate score overridden successfully.");
      setOverrideOpen(false);
      setOverrideScore("");
      setOverrideReason("");
      onUpdate();
    } catch (err) {
      toast.error("Failed to override score.");
    } finally {
      setOverrideLoading(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Status Dropdown */}
      <div className="relative flex items-center">
        <select
          value={candidate.hr_status || "Applied"}
          onChange={handleStatusChange}
          disabled={statusLoading}
          className="h-8 rounded-md border border-white/10 bg-background pl-2 pr-8 text-xs font-medium text-white focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50 appearance-none"
        >
          {HR_STATUSES.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </select>
        <ChevronDown className="absolute right-2 h-3.5 w-3.5 pointer-events-none text-gray-400" />
      </div>

      {/* Add Note Button */}
      <Button
        variant="outline"
        size="sm"
        className="h-8 gap-1 text-xs"
        onClick={onToggleNote}
      >
        <MessageSquare className="h-3.5 w-3.5" /> Note
      </Button>

      {/* Override Score Button */}
      <Button
        variant="outline"
        size="sm"
        className="h-8 gap-1 text-xs text-amber-400 border-amber-500/20 hover:bg-amber-500/10 hover:text-amber-300"
        onClick={() => setOverrideOpen(true)}
      >
        <ShieldAlert className="h-3.5 w-3.5" /> Score
      </Button>

      {/* View Timeline Button */}
      <Button
        variant="outline"
        size="sm"
        className="h-8 gap-1 text-xs text-blue-400 border-blue-500/20 hover:bg-blue-500/10 hover:text-blue-300"
        onClick={() => setTimelineOpen(true)}
      >
        <History className="h-3.5 w-3.5" /> Timeline
      </Button>

      {/* Score Override Dialog */}
      <Dialog open={overrideOpen} onOpenChange={setOverrideOpen}>
        <DialogContent className="max-w-md bg-gray-950 text-white border-white/10">
          <DialogHeader>
            <DialogTitle>Override Candidate Score</DialogTitle>
            <DialogDescription className="text-gray-400">
              Override the machine-evaluated score for {candidate.name || candidate.filename}. This override will take precedence in leaderboard sorting.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleOverrideSubmit} className="space-y-4 py-2">
            <div className="space-y-1">
              <label htmlFor="score-input" className="text-xs font-semibold text-gray-300">
                Override Score (0.0 - 100.0)
              </label>
              <Input
                id="score-input"
                type="number"
                step="0.1"
                min="0"
                max="100"
                value={overrideScore}
                onChange={(e) => setOverrideScore(e.target.value)}
                placeholder="e.g. 85.5"
                required
                className="bg-background border-white/10 text-white text-sm"
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="reason-input" className="text-xs font-semibold text-gray-300">
                Reason for Override
              </label>
              <Input
                id="reason-input"
                type="text"
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                placeholder="e.g. Verified project links and deep backend experience"
                required
                className="bg-background border-white/10 text-white text-sm"
              />
            </div>
            <DialogFooter className="pt-2">
              <DialogClose asChild>
                <Button variant="ghost" type="button" className="text-xs">
                  Cancel
                </Button>
              </DialogClose>
              <Button type="submit" disabled={overrideLoading} size="sm" className="text-xs bg-amber-500 hover:bg-amber-600 text-black font-semibold">
                {overrideLoading ? "Overriding..." : "Confirm Override"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Slide-over Timeline Drawer */}
      <CandidateTimeline
        candidateId={candidate.id}
        candidateName={candidate.name || candidate.filename}
        isOpen={timelineOpen}
        onClose={() => setTimelineOpen(false)}
      />
    </div>
  );
};

export default CandidateActions;
