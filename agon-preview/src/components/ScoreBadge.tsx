import { tierFromScore } from '../lib/types';

interface ScoreBadgeProps {
  score: number;
  size?: 'sm' | 'md';
  label?: string;
}

const tierConfig = {
  strong: { color: '#34C28A', text: 'Hire' },
  promising: { color: '#F5B544', text: 'Consider' },
  weak: { color: '#F25C7C', text: 'Reject' },
};

export function ScoreBadge({ score, size = 'md', label }: ScoreBadgeProps) {
  const tier = tierFromScore(score);
  const cfg = tierConfig[tier];
  const padding = size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-3 py-1 text-sm';

  return (
    <span
      className={`tnum inline-flex items-center gap-1.5 rounded-full font-mono font-semibold ${padding}`}
      style={{ background: `${cfg.color}26`, color: cfg.color, border: `1px solid ${cfg.color}59` }}
    >
      <span className="font-bold">{score}</span>
      {label && <span className="opacity-80">{label}</span>}
    </span>
  );
}
