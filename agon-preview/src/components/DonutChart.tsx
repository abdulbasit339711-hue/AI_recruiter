import { motion } from 'framer-motion';

interface DonutSlice {
  label: string;
  value: number;
  color: string;
}

interface DonutChartProps {
  data: DonutSlice[];
  size?: number;
  thickness?: number;
  centerLabel?: string;
  centerValue?: number;
}

export function DonutChart({ data, size = 160, thickness = 22, centerLabel, centerValue }: DonutChartProps) {
  const total = data.reduce((s, d) => s + d.value, 0);
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  let acc = 0;

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:gap-6">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth={thickness} />
          {data.map((slice, i) => {
            const frac = slice.value / total;
            const dash = c * frac;
            const gap = c - dash;
            const offset = -acc * c;
            acc += frac;
            return (
              <motion.circle
                key={slice.label}
                cx={size / 2}
                cy={size / 2}
                r={r}
                fill="none"
                stroke={slice.color}
                strokeWidth={thickness}
                strokeDasharray={`${dash} ${gap}`}
                strokeDashoffset={offset}
                initial={{ opacity: 0, strokeDasharray: `0 ${c}` }}
                animate={{ opacity: 1, strokeDasharray: `${dash} ${gap}` }}
                transition={{ duration: 1, delay: i * 0.15, ease: [0.22, 1, 0.36, 1] }}
                style={{ filter: `drop-shadow(0 0 4px ${slice.color}40)` }}
              />
            );
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {centerValue !== undefined && (
            <span className="tnum font-mono text-2xl font-bold text-heading">{centerValue}</span>
          )}
          {centerLabel && <span className="mt-0.5 text-[10px] uppercase tracking-wider text-muted">{centerLabel}</span>}
        </div>
      </div>
      <div className="flex flex-col gap-2">
        {data.map((slice) => (
          <div key={slice.label} className="flex items-center gap-2.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: slice.color, boxShadow: `0 0 6px ${slice.color}80` }} />
            <span className="text-xs text-muted">{slice.label}</span>
            <span className="tnum ml-auto font-mono text-xs font-semibold text-heading">{slice.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
