import type { CandidateStatus } from "@/types";

const STATUS_STYLES: Record<string, string> = {
  Queued: "border-sky-400/25 bg-sky-400/10 text-sky-200",
  Processing: "border-cyan-400/25 bg-cyan-400/10 text-cyan-200",
  Shortlisted: "border-emerald-400/25 bg-emerald-400/10 text-emerald-200",
  Reviewed: "border-amber-400/25 bg-amber-400/10 text-amber-200",
  Rejected: "border-rose-400/25 bg-rose-400/10 text-rose-200",
  Ungraded: "border-slate-400/25 bg-slate-400/10 text-slate-200",
  Error: "border-red-400/25 bg-red-400/10 text-red-200",
  Pending: "border-sky-400/25 bg-sky-400/10 text-sky-200",
  Processed: "border-emerald-400/25 bg-emerald-400/10 text-emerald-200",
  Failed: "border-red-400/25 bg-red-400/10 text-red-200",
  Active: "border-emerald-400/25 bg-emerald-400/10 text-emerald-200",
  Archived: "border-slate-400/25 bg-slate-400/10 text-slate-200",
};

export function StatusBadge({ status }: { status: CandidateStatus | "Active" | "Archived" | string }) {
  return (
    <span
      className={`inline-flex h-6 items-center rounded-full border px-2.5 text-xs font-medium ${
        STATUS_STYLES[status] ?? "border-white/15 bg-white/5 text-muted-foreground"
      }`}
    >
      {status}
    </span>
  );
}
