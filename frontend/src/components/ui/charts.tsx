"use client";

/**
 * Animated, theme-aware chart primitives — pure SVG + framer-motion (no chart lib).
 *
 * Everything reads the design tokens (var(--primary), var(--strong), …) so charts
 * recolor automatically in light/dark. Animations are GPU-friendly (transform /
 * pathLength / opacity) and respect prefers-reduced-motion via framer-motion's
 * reduced-motion handling. Built for the recruiter score data: count-ups, radial
 * gauges, donuts, bars, and sparklines.
 */

import React, { useEffect, useRef, useState } from "react";
import {
  motion,
  useInView,
  useReducedMotion,
  animate,
} from "framer-motion";

const EASE = [0.22, 1, 0.36, 1] as const;

/* ---------------------------------------------------------------- CountUp */
export function CountUp({
  value,
  decimals = 0,
  duration = 1.1,
  suffix = "",
  className,
}: {
  value: number;
  decimals?: number;
  duration?: number;
  suffix?: string;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const reduce = useReducedMotion();
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (!inView) return;
    if (reduce) {
      setDisplay(value);
      return;
    }
    const controls = animate(0, value, {
      duration,
      ease: EASE,
      onUpdate: (v) => setDisplay(v),
    });
    return () => controls.stop();
  }, [inView, value, duration, reduce]);

  return (
    <span ref={ref} className={className} style={{ fontVariantNumeric: "tabular-nums" }}>
      {display.toFixed(decimals)}
      {suffix}
    </span>
  );
}

/* ------------------------------------------------------------ RadialGauge */
/** A single-value arc gauge (e.g. average score /max). */
export function RadialGauge({
  value,
  max = 100,
  size = 132,
  stroke = 11,
  color,
  label,
  sublabel,
}: {
  value: number;
  max?: number;
  size?: number;
  stroke?: number;
  color?: string;
  label?: string;
  sublabel?: string;
}) {
  const ref = useRef<SVGSVGElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const reduce = useReducedMotion();
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, value / max));

  // 270° arc, rotated 135° so gap sits at the bottom-left/right.
  const arcFraction = 0.75;
  const arcLength = c * arcFraction;
  const trackOffset = arcLength - pct * arcLength;

  // Tier-based coloring when no explicit color is provided.
  const resolvedColor =
    color ??
    (value >= 70 ? "#34C28A" : value >= 40 ? "#F5B544" : "#F25C7C");

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg ref={ref} width={size} height={size} className="block" style={{ transform: "rotate(135deg)" }}>
        {/* Track (background arc) */}
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={`${arcLength} ${c}`}
        />
        {/* Animated fill arc */}
        <motion.circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke={resolvedColor} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={`${arcLength} ${c}`}
          initial={{ strokeDashoffset: arcLength }}
          animate={inView ? { strokeDashoffset: trackOffset } : {}}
          transition={{ duration: reduce ? 0 : 1.4, ease: [0.22, 1, 0.36, 1], delay: reduce ? 0 : 0.1 }}
          style={{ filter: `drop-shadow(0 0 6px ${resolvedColor}55)` }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-2xl font-semibold text-heading">
          <CountUp value={value} decimals={value % 1 ? 1 : 0} />
        </span>
        {label && <span className="mt-0.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</span>}
        {sublabel && <span className="text-[10px] text-faint">{sublabel}</span>}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Donut */
type Slice = { label: string; value: number; color: string };

export function Donut({
  data,
  size = 150,
  stroke = 18,
}: {
  data: Slice[];
  size?: number;
  stroke?: number;
}) {
  const ref = useRef<SVGSVGElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const reduce = useReducedMotion();
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  let acc = 0;

  return (
    <svg ref={ref} width={size} height={size} className="block -rotate-90">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke="color-mix(in srgb, var(--foreground) 8%, transparent)" strokeWidth={stroke} />
      {data.map((d, i) => {
        const frac = d.value / total;
        const len = c * frac;
        const offset = c * (acc / total);
        acc += d.value;
        return (
          <motion.circle
            key={d.label}
            cx={size / 2} cy={size / 2} r={r} fill="none"
            stroke={d.color} strokeWidth={stroke}
            strokeDasharray={`${len} ${c}`}
            strokeDashoffset={-offset}
            initial={{ opacity: 0, strokeDasharray: `0 ${c}` }}
            animate={inView ? { opacity: 1, strokeDasharray: `${len} ${c}` } : {}}
            transition={{ duration: reduce ? 0 : 0.9, ease: EASE, delay: reduce ? 0 : i * 0.12 }}
            strokeLinecap="butt"
          />
        );
      })}
    </svg>
  );
}

/* -------------------------------------------------------------- BarChart */
/** Horizontal bars; values animate in width. */
export function BarChart({
  data,
  formatValue = (v) => String(v),
}: {
  data: { label: string; value: number; color?: string }[];
  formatValue?: (v: number) => string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const reduce = useReducedMotion();
  const max = Math.max(...data.map((d) => d.value), 1);

  return (
    <div ref={ref} className="space-y-3.5">
      {data.map((d, i) => (
        <div key={d.label} className="grid grid-cols-[96px_1fr_auto] items-center gap-3 text-sm">
          <span className="truncate text-muted-foreground">{d.label}</span>
          <div className="h-2.5 overflow-hidden rounded-full bg-foreground/[0.07]">
            <motion.div
              className="h-full rounded-full"
              style={{
                background: `linear-gradient(90deg, ${d.color || "var(--primary)"}, ${(d.color || "var(--primary)") + "cc"})`,
                boxShadow: `0 0 12px ${(d.color || "var(--primary)") + "40"}`,
              }}
              initial={{ width: 0 }}
              animate={inView ? { width: `${(d.value / max) * 100}%` } : {}}
              transition={{ duration: reduce ? 0 : 0.9, ease: EASE, delay: reduce ? 0 : i * 0.08 }}
            />
          </div>
          <span className="w-10 text-right font-mono text-xs font-semibold text-heading tabular-nums">
            {formatValue(d.value)}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------- Histogram */
/** Vertical bars for a distribution (e.g. score buckets). */
export function Histogram({
  bins,
  color = "var(--primary)",
  height = 120,
}: {
  bins: { label: string; value: number }[];
  color?: string;
  height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const reduce = useReducedMotion();
  const max = Math.max(...bins.map((b) => b.value), 1);

  return (
    <div ref={ref} className="flex items-end gap-1.5" style={{ height }}>
      {bins.map((b, i) => (
        <div key={b.label} className="flex flex-1 flex-col items-center gap-1.5">
          <div className="flex w-full flex-1 items-end">
            <motion.div
              className="w-full rounded-t-md"
              style={{ background: `linear-gradient(180deg, ${color}, color-mix(in srgb, ${color} 55%, transparent))` }}
              initial={{ height: 0 }}
              animate={inView ? { height: `${(b.value / max) * 100}%` } : {}}
              transition={{ duration: reduce ? 0 : 0.8, ease: EASE, delay: reduce ? 0 : i * 0.05 }}
            />
          </div>
          <span className="font-mono text-[10px] text-faint">{b.label}</span>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------- Sparkline */
export function Sparkline({
  points,
  width = 120,
  height = 36,
  color = "var(--primary)",
}: {
  points: number[];
  width?: number;
  height?: number;
  color?: string;
}) {
  const ref = useRef<SVGSVGElement>(null);
  const inView = useInView(ref, { once: true });
  const reduce = useReducedMotion();
  if (points.length < 2) return null;
  const max = Math.max(...points);
  const min = Math.min(...points);
  const span = max - min || 1;
  const step = width / (points.length - 1);
  const coords = points.map((p, i) => [i * step, height - ((p - min) / span) * (height - 4) - 2]);
  const line = coords.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${line} L${width},${height} L0,${height} Z`;

  return (
    <svg ref={ref} width={width} height={height} className="block">
      <defs>
        <linearGradient id="spark" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <motion.path d={area} fill="url(#spark)"
        initial={{ opacity: 0 }} animate={inView ? { opacity: 1 } : {}} transition={{ duration: 0.8, delay: 0.3 }} />
      <motion.path d={line} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
        initial={{ pathLength: 0 }} animate={inView ? { pathLength: 1 } : {}}
        transition={{ duration: reduce ? 0 : 1.1, ease: EASE }} />
    </svg>
  );
}
