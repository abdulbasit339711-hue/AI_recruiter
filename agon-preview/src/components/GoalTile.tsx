import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown } from 'lucide-react';

interface GoalTileProps {
  title: string;
  coverage: number; // 0-100
  outcome: 'Passed' | 'Partial' | 'Failed';
}

const outcomeConfig = {
  Passed: { color: '#34C28A', label: 'Passed' },
  Partial: { color: '#F5B544', label: 'Partial' },
  Failed: { color: '#F25C7C', label: 'Failed' },
};

export function GoalTile({ title, coverage, outcome }: GoalTileProps) {
  const [open, setOpen] = useState(false);
  const cfg = outcomeConfig[outcome];
  const size = 54;
  const stroke = 5;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - coverage / 100);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="glass glass-hover rounded-2xl p-4 cursor-pointer"
      onClick={() => setOpen((o) => !o)}
    >
      <div className="flex items-start gap-3">
        <div className="relative shrink-0" style={{ width: size, height: size }}>
          <svg width={size} height={size} className="-rotate-90">
            <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={stroke} />
            <motion.circle
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={cfg.color}
              strokeWidth={stroke}
              strokeLinecap="round"
              strokeDasharray={c}
              initial={{ strokeDashoffset: c }}
              animate={{ strokeDashoffset: offset }}
              transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1] }}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="tnum font-mono text-[11px] font-bold" style={{ color: cfg.color }}>{coverage}%</span>
          </div>
        </div>
        <div className="min-w-0 flex-1">
          <h4 className="text-sm font-medium text-heading leading-snug">{title}</h4>
          <span
            className="mt-1 inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
            style={{ background: `${cfg.color}26`, color: cfg.color, border: `1px solid ${cfg.color}40` }}
          >
            {cfg.label}
          </span>
        </div>
        <ChevronDown className={`mt-0.5 h-4 w-4 shrink-0 text-faint transition-transform ${open ? 'rotate-180' : ''}`} />
      </div>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-3 pt-3 border-t border-white/[0.06]">
              <p className="text-xs text-muted leading-relaxed">
                Coverage assessed at <span className="font-mono tnum" style={{ color: cfg.color }}>{coverage}%</span>.
                The candidate demonstrated {outcome === 'Passed' ? 'strong command' : outcome === 'Partial' ? 'partial command' : 'insufficient command'} of this competency area during the live interview session.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
