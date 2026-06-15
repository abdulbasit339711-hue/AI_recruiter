import React from "react";

interface StatusBadgeProps {
  status: string | null;
}

const COLOR_MAP: Record<string, string> = {
  Applied: "bg-foreground/5 text-muted-foreground border-border",
  Screened: "bg-blue-500/10 text-blue-700 dark:text-blue-300 border-blue-500/20",
  Interview: "bg-violet-500/10 text-violet-700 dark:text-violet-300 border-violet-500/20",
  Offer: "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/20",
  Hired: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/20",
  Rejected: "bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/20",
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const displayStatus = status || "Applied";
  const colorClass = COLOR_MAP[displayStatus] || COLOR_MAP.Applied;

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold transition-colors duration-200 ${colorClass}`}
    >
      {displayStatus}
    </span>
  );
};

export default StatusBadge;
