import { motion } from 'framer-motion';
import { tierFromScore } from '../lib/types';

interface BarChartItem {
  label: string;
  value: number; // 0-100
  displayValue?: string;
}

interface BarChartProps {
  items: BarChartItem[];
  className?: string;
  compact?: boolean;
}

const tierColors = {
  strong: '#34C28A',
  promising: '#F5B544',
  weak: '#F25C7C',
};

export function BarChart({ items, className = '', compact = false }: BarChartProps) {
  return (
    <div className={`flex flex-col ${compact ? 'gap-2' : 'gap-3.5'} ${className}`}>
      {items.map((item, i) => {
        const tier = tierFromScore(item.value);
        const color = tierColors[tier];
        const tint = `${color}26`; // 15% tint
        return (
          <div key={item.label} className="w-full">
            <div className="flex items-center justify-between mb-1">
              <span className={`text-muted ${compact ? 'text-[11px]' : 'text-sm'}`}>{item.label}</span>
              <span className={`tnum font-mono font-semibold ${compact ? 'text-[11px]' : 'text-sm'}`} style={{ color }}>
                {item.displayValue ?? `${item.value}%`}
              </span>
            </div>
            <div className="h-2 w-full rounded-full bg-white/[0.04] overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${item.value}%` }}
                transition={{ duration: 1, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] }}
                className="h-full rounded-full"
                style={{ background: `linear-gradient(90deg, ${color}, ${color}cc)`, boxShadow: `0 0 12px ${color}40` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
