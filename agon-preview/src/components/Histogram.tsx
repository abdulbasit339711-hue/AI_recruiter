import { motion } from 'framer-motion';
import { tierFromScore } from '../lib/types';

interface HistogramProps {
  buckets: { label: string; count: number }[];
  className?: string;
}

const tierColors = {
  strong: '#34C28A',
  promising: '#F5B544',
  weak: '#F25C7C',
};

// Map bucket index to a score midpoint for tier coloring
const bucketMidpoints = [10, 30, 50, 70, 90];

export function Histogram({ buckets, className = '' }: HistogramProps) {
  const max = Math.max(...buckets.map((b) => b.count), 1);
  return (
    <div className={`flex h-full items-end gap-3 ${className}`}>
      {buckets.map((bucket, i) => {
        const tier = tierFromScore(bucketMidpoints[i]);
        const color = tierColors[tier];
        const heightPct = (bucket.count / max) * 100;
        return (
          <div key={bucket.label} className="flex flex-1 flex-col items-center gap-2">
            <span className="tnum font-mono text-xs font-semibold" style={{ color }}>{bucket.count}</span>
            <div className="relative w-full flex-1 rounded-lg bg-white/[0.03]" style={{ minHeight: 120 }}>
              <motion.div
                initial={{ height: 0 }}
                animate={{ height: `${heightPct}%` }}
                transition={{ duration: 1, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] }}
                className="absolute bottom-0 left-0 right-0 rounded-lg"
                style={{ background: `linear-gradient(180deg, ${color}, ${color}99)`, boxShadow: `0 0 16px ${color}33` }}
              />
            </div>
            <span className="text-[10px] text-faint">{bucket.label}</span>
          </div>
        );
      })}
    </div>
  );
}
