"use client";

/**
 * Shared framer-motion primitives for richer, consistent animation across pages.
 * All respect prefers-reduced-motion (framer-motion zeroes transitions globally
 * when the user opts out). Keep these GPU-friendly (transform/opacity only).
 */

import React from "react";
import { motion, AnimatePresence } from "framer-motion";

const EASE = [0.22, 1, 0.36, 1] as const;

/** Entrance fade + rise. `delay` in seconds. */
export function FadeIn({
  children, delay = 0, y = 16, className, as = "div",
}: {
  children: React.ReactNode; delay?: number; y?: number; className?: string;
  as?: "div" | "section" | "li" | "header";
}) {
  const M = (motion as any)[as] ?? motion.div;
  return (
    <M
      className={className}
      initial={{ opacity: 0, y }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, ease: EASE, delay }}
    >
      {children}
    </M>
  );
}

/** Stagger container — wrap StaggerItem children. */
export function Stagger({
  children, className, gap = 0.08, delay = 0,
}: {
  children: React.ReactNode; className?: string; gap?: number; delay?: number;
}) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="visible"
      variants={{ hidden: {}, visible: { transition: { staggerChildren: gap, delayChildren: delay } } }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children, className, y = 14,
}: {
  children: React.ReactNode; className?: string; y?: number;
}) {
  return (
    <motion.div
      className={className}
      variants={{
        hidden: { opacity: 0, y },
        visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } },
      }}
    >
      {children}
    </motion.div>
  );
}

/** Smoothly cross-fades between keyed content (e.g. wizard steps, phases). */
export function Swap({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={k}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        transition={{ duration: 0.35, ease: EASE }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

/** Animated equalizer bars — shown when a participant is actively speaking. */
export function SpeakingBars({
  active, color = "currentColor", bars = 4, className,
}: {
  active: boolean; color?: string; bars?: number; className?: string;
}) {
  return (
    <span className={className} style={{ display: "inline-flex", alignItems: "center", gap: 2, height: 14 }} aria-hidden>
      {Array.from({ length: bars }).map((_, i) => (
        <motion.span
          key={i}
          style={{ width: 3, borderRadius: 2, background: color, display: "block" }}
          animate={
            active
              ? { height: [4, 13, 6, 14, 5], opacity: 1 }
              : { height: 3, opacity: 0.4 }
          }
          transition={
            active
              ? { duration: 0.9, repeat: Infinity, ease: "easeInOut", delay: i * 0.12 }
              : { duration: 0.2 }
          }
        />
      ))}
    </span>
  );
}
