import React from "react";

interface StatusBadgeProps {
  status: string | null;
}

const COLOR_MAP: Record<string, string> = {
  Applied: "bg-gray-500/10 text-gray-400 border-gray-500/20",
  Screened: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  Interview: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  Offer: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  Hired: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  Rejected: "bg-rose-500/10 text-rose-400 border-rose-500/20",
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const displayStatus = status || "Applied";
  const colorClass = COLOR_MAP[displayStatus] || "bg-gray-500/10 text-gray-400 border-gray-500/20";

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold transition-colors duration-200 ${colorClass}`}
    >
      {displayStatus}
    </span>
  );
};

export default StatusBadge;
