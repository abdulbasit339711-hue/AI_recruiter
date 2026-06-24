import { motion } from 'framer-motion';
import { tierFromScore } from '../lib/types';

interface RadialGaugeProps {
  value: number; // 0-100
  size?: number;
  label?: string;
  sublabel?: string;
  showValue?: boolean;
  strokeWidth?: number;
}

const tierColors = {
  strong: '#34C28A',
  promising: '#F5B544',
  weak: '#F25C7C',
};

export function RadialGauge({
  value,
  size = 120,
  label,
  sublabel,
  showValue = true,
  strokeWidth = 10,
}: RadialGaugeProps) {
  const tier = tierFromScore(value);
  const color = tierColors[tier];
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const arcFraction = 0.75;
  const arcLength = circumference * arcFraction;
  const offset = arcLength * (1 - value / 100);
  const center = size / 2;
  const rotation = 135;

  return (
    <div className="relative inline-flex flex-col items-center" style={{ width: size }}>
      <svg width={size} height={size} className="overflow-visible">
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={`${arcLength} ${circumference}`}
          transform={`rotate(${rotation} ${center} ${center})`}
        />
        <motion.circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={`${arcLength} ${circumference}`}
          transform={`rotate(${rotation} ${center} ${center})`}
          initial={{ strokeDashoffset: arcLength }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.4, ease: [0.22, 1, 0.36, 1] }}
          style={{ filter: `drop-shadow(0 0 6px ${color}55)` }}
        />
      </svg>
      {showValue && (
        <div className="absolute inset-0 flex flex-col items-center justify-center" style={{ pointerEvents: 'none' }}>
          <span className="tnum font-mono font-bold leading-none" style={{ fontSize: size * 0.22, color }}>
            {Math.round(value)}
          </span>
          {label && (
            <span className="mt-1 text-[10px] uppercase tracking-wider text-muted">{label}</span>
          )}
        </div>
      )}
      {sublabel && <span className="mt-2 text-xs text-faint">{sublabel}</span>}
    </div>
  );
}
