import type { CandidateStatus } from '../lib/types';

const statusConfig: Record<CandidateStatus, { color: string }> = {
  'Pending Review': { color: '#F5B544' },
  Shortlisted: { color: '#1C99BF' },
  'In Interview': { color: '#3DAFCC' },
  Hired: { color: '#34C28A' },
  Rejected: { color: '#F25C7C' },
  Archived: { color: '#556070' },
};

export function StatusPill({ status }: { status: CandidateStatus }) {
  const cfg = statusConfig[status];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium"
      style={{ background: `${cfg.color}26`, color: cfg.color, border: `1px solid ${cfg.color}33` }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: cfg.color, boxShadow: `0 0 6px ${cfg.color}80` }} />
      {status}
    </span>
  );
}
