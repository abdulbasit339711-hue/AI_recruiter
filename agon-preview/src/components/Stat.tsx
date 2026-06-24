import { motion } from 'framer-motion';
import { CountUp } from './CountUp';

interface StatProps {
  label: string;
  value: number;
  suffix?: string;
  decimals?: number;
  accentColor?: string; // bottom border strip color
  icon?: React.ReactNode;
  delay?: number;
}

export function Stat({
  label,
  value,
  suffix = '',
  decimals = 0,
  accentColor = '#1C99BF',
  icon,
  delay = 0,
}: StatProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: [0.22, 1, 0.36, 1] }}
      className="glass relative overflow-hidden rounded-2xl p-5"
    >
      <div
        className="absolute bottom-0 left-0 right-0 h-[3px]"
        style={{ background: accentColor, boxShadow: `0 0 12px ${accentColor}80` }}
      />
      <div className="flex items-start justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-muted">{label}</span>
        {icon && <span style={{ color: accentColor }}>{icon}</span>}
      </div>
      <div className="mt-3 flex items-baseline gap-1">
        <span className="tnum font-mono text-3xl font-bold text-heading">
          <CountUp value={value} decimals={decimals} suffix={suffix} />
        </span>
      </div>
    </motion.div>
  );
}
