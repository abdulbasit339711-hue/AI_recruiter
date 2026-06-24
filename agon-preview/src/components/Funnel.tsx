import { motion } from 'framer-motion';

interface FunnelProps {
  stages: { label: string; value: number; color?: string }[];
}

export function Funnel({ stages }: FunnelProps) {
  const max = Math.max(...stages.map((s) => s.value), 1);
  return (
    <div className="flex flex-col gap-4">
      {stages.map((stage, i) => {
        const color = stage.color ?? '#1C99BF';
        const widthPct = (stage.value / max) * 100;
        return (
          <div key={stage.label}>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-sm text-muted">{stage.label}</span>
              <span className="tnum font-mono text-sm font-semibold text-heading">{stage.value}</span>
            </div>
            <div className="h-2.5 w-full rounded-full bg-white/[0.04] overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${widthPct}%` }}
                transition={{ duration: 1.1, delay: i * 0.15, ease: [0.22, 1, 0.36, 1] }}
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
