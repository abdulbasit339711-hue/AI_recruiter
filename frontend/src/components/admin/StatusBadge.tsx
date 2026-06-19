type StatusBadgeProps = {
  status: string;
};

function statusColor(status: string): string {
  const s = status.toLowerCase();
  if (s === "hired" || s === "strong") return "#34C28A";
  if (s === "processed" || s === "shortlisted" || s === "in interview") return "#1C99BF";
  if (s === "pending" || s === "pending review" || s === "promising") return "#F5B544";
  if (s === "failed" || s === "rejected" || s === "weak") return "#F25C7C";
  if (s === "archived") return "#556070";
  return "#9CA3B0";
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const color = statusColor(status);
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium"
      style={{
        background: `${color}26`,
        color,
        border: `1px solid ${color}33`,
      }}
    >
      <span
        className="h-1.5 w-1.5 rounded-full shrink-0"
        style={{
          background: color,
          boxShadow: `0 0 6px ${color}80`,
        }}
      />
      {status}
    </span>
  );
}

export default StatusBadge;
