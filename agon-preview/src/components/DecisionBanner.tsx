import { motion } from 'framer-motion';
import { tierFromScore } from '../lib/types';

interface DecisionBannerProps {
  decision: 'HIRE' | 'CONSIDER' | 'REJECT';
  score: number;
  rationale: string;
  delay?: number;
}

const decisionConfig = {
  HIRE: { color: '#34C28A', label: 'HIRE', tierLabel: 'Strong' },
  CONSIDER: { color: '#F5B544', label: 'CONSIDER', tierLabel: 'Promising' },
  REJECT: { color: '#F25C7C', label: 'REJECT', tierLabel: 'Weak' },
};

export function DecisionBanner({ decision, score, rationale, delay = 0 }: DecisionBannerProps) {
  const cfg = decisionConfig[decision];
  return (
    <motion.div
      initial={{ opacity: 0, x: -16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, delay, ease: [0.22, 1, 0.36, 1] }}
      className="glass rounded-2xl overflow-hidden"
      style={{ borderLeft: `6px solid ${cfg.color}` }}
    >
      <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center">
        <div className="flex items-center gap-3 shrink-0">
          <span
            className="tnum inline-flex items-center rounded-lg px-3 py-1.5 font-mono text-lg font-bold"
            style={{ background: `${cfg.color}26`, color: cfg.color, border: `1px solid ${cfg.color}59` }}
          >
            {score}
          </span>
          <span
            className="inline-flex items-center rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wider"
            style={{ background: `${cfg.color}26`, color: cfg.color, border: `1px solid ${cfg.color}59` }}
          >
            {cfg.label}
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm leading-relaxed text-muted">
            <span className="font-semibold text-heading">AI Rationale — </span>
            {rationale}
          </p>
        </div>
      </div>
    </motion.div>
  );
}
