"use client";

import { motion } from "framer-motion";
import { ReactNode } from "react";
import { CountUp } from "@/components/ui/charts";

interface StatProps {
  label: string;
  value: number;
  suffix?: string;
  decimals?: number;
  accentColor?: string;
  icon?: ReactNode;
  delay?: number;
}

export function Stat({
  label,
  value,
  suffix,
  decimals = 0,
  accentColor = "#1C99BF",
  icon,
  delay = 0,
}: StatProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: [0.22, 1, 0.36, 1] }}
      className="relative overflow-hidden rounded-2xl p-5"
      style={{
        background: "rgba(8,34,52,0.7)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        border: "1px solid rgba(255,255,255,0.08)",
      }}
    >
      {/* Colored bottom strip */}
      <div
        className="absolute bottom-0 left-0 right-0 h-[3px]"
        style={{
          background: accentColor,
          boxShadow: `0 0 12px ${accentColor}80`,
        }}
      />

      {/* Top row: label + icon */}
      <div className="flex items-start justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        {icon && (
          <span style={{ color: accentColor }} className="opacity-80">
            {icon}
          </span>
        )}
      </div>

      {/* Value */}
      <div className="mt-3 flex items-baseline gap-1">
        <span
          className="font-mono text-3xl font-bold tabular-nums"
          style={{ color: "var(--heading)" }}
        >
          <CountUp value={value} decimals={decimals} />
        </span>
        {suffix && (
          <span className="text-sm text-muted-foreground">{suffix}</span>
        )}
      </div>
    </motion.div>
  );
}
