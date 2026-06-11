"use client";

import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Loader2, SlidersHorizontal } from "lucide-react";

import { api } from "@/lib/api";

type Weights = { tier1_weight: number; tier2_weight: number; tier3_weight: number };
const DEFAULTS: Weights = { tier1_weight: 1, tier2_weight: 1, tier3_weight: 1 };

/**
 * Compact per-job scoring-weight editor. Tier scores are multiplied by these weights
 * in the final total (1.0 = unchanged). Saving applies to FUTURE scoring, so it offers
 * to reprocess the job's candidates to recompute existing totals.
 */
export function ScoringWeightsEditor({ jobId }: { jobId: number }) {
  const [open, setOpen] = useState(false);
  const [w, setW] = useState<Weights>(DEFAULTS);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setW(await api.getScoringWeights(jobId));
    } catch {
      setW(DEFAULTS);
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  async function save(reprocess: boolean) {
    setSaving(true);
    try {
      await api.setScoringWeights(jobId, w);
      if (reprocess) {
        await api.reprocessJobCandidates(jobId);
        toast.success("Weights saved — re-scoring all candidates");
      } else {
        toast.success("Weights saved (reprocess to recompute totals)");
      }
      setOpen(false);
    } catch (e) {
      toast.error((e as { message?: string })?.message || "Failed to save weights");
    } finally {
      setSaving(false);
    }
  }

  const field = (key: keyof Weights, label: string) => (
    <label className="flex flex-col gap-1 text-xs text-muted-foreground">
      {label}
      <input
        type="number"
        min={0}
        max={5}
        step={0.1}
        value={w[key]}
        onChange={(e) => setW({ ...w, [key]: Number(e.target.value) })}
        className="h-9 w-20 rounded-md border border-white/10 bg-background px-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
      />
    </label>
  );

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 rounded-md border border-white/10 px-3 py-1.5 text-xs font-medium hover:bg-white/5"
      >
        <SlidersHorizontal className="h-4 w-4" /> Weights
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-2 w-72 rounded-xl border border-white/10 bg-popover p-4 shadow-xl">
          <p className="mb-3 text-xs text-muted-foreground">
            Tier multipliers for the final score (1.0 = unchanged).
          </p>
          {loading ? (
            <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading…
            </div>
          ) : (
            <>
              <div className="flex items-end justify-between gap-2">
                {field("tier1_weight", "Tier 1")}
                {field("tier2_weight", "Tier 2")}
                {field("tier3_weight", "Tier 3")}
              </div>
              <div className="mt-4 flex justify-end gap-2">
                <button
                  onClick={() => save(false)}
                  disabled={saving}
                  className="rounded-md border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-60"
                >
                  Save
                </button>
                <button
                  onClick={() => save(true)}
                  disabled={saving}
                  className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500 disabled:opacity-60"
                >
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  Save & re-score
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
