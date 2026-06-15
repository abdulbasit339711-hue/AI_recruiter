import type { CandidateStatus } from "@/types";

// Tints tuned to read on the light base; `dark:` brightens text for the dark toggle.
const STATUS_STYLES: Record<string, string> = {
  Queued: "border-sky-500/20 bg-sky-500/10 text-sky-700 dark:text-sky-300",
  Processing: "border-cyan-500/20 bg-cyan-500/10 text-cyan-700 dark:text-cyan-300",
  Shortlisted: "border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  Reviewed: "border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  Rejected: "border-rose-500/20 bg-rose-500/10 text-rose-700 dark:text-rose-300",
  Ungraded: "border-slate-500/20 bg-slate-500/10 text-slate-600 dark:text-slate-300",
  Error: "border-red-500/20 bg-red-500/10 text-red-700 dark:text-red-300",
  Pending: "border-sky-500/20 bg-sky-500/10 text-sky-700 dark:text-sky-300",
  Processed: "border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  Failed: "border-red-500/20 bg-red-500/10 text-red-700 dark:text-red-300",
  Active: "border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  Archived: "border-slate-500/20 bg-slate-500/10 text-slate-600 dark:text-slate-300",
};

export function StatusBadge({ status }: { status: CandidateStatus | "Active" | "Archived" | string }) {
  return (
    <span
      className={`inline-flex h-5 items-center rounded-full border px-2 text-[11px] font-medium ${
        STATUS_STYLES[status] ?? "border-border bg-foreground/5 text-muted-foreground"
      }`}
    >
      {status}
    </span>
  );
}
