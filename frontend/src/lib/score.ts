// src/lib/score.ts
// Plain-language score semantics, shared across dashboard, detail, and applicant flow.
// Color-blind safe: every tier pairs a color with a distinct icon + word.

export type ScoreTier = "strong" | "promising" | "weak";

export interface ScoreMeta {
  tier: ScoreTier;
  /** Plain-language label shown to non-technical HR users. */
  label: "Strong" | "Promising" | "Weak";
  /** Tailwind/utility class for the pill background+text. */
  chipClass: string;
  /** CSS custom property name for the tier's solid color. */
  colorVar: string;
}

/** Thresholds match the design spec: 80–100 strong · 55–79 promising · <55 weak. */
export function scoreTier(score: number | null | undefined): ScoreTier {
  const s = score ?? 0;
  if (s >= 80) return "strong";
  if (s >= 55) return "promising";
  return "weak";
}

export function scoreMeta(score: number | null | undefined): ScoreMeta {
  const tier = scoreTier(score);
  switch (tier) {
    case "strong":
      return { tier, label: "Strong", chipClass: "chip chip-strong", colorVar: "var(--strong)" };
    case "promising":
      return { tier, label: "Promising", chipClass: "chip chip-promising", colorVar: "var(--promising)" };
    default:
      return { tier, label: "Weak", chipClass: "chip chip-weak", colorVar: "var(--weak)" };
  }
}

/** A short, reassuring sentence for the candidate headline. */
export function recommendationCopy(score: number | null | undefined): string {
  switch (scoreTier(score)) {
    case "strong":
      return "Strong match — recommended to move to interview.";
    case "promising":
      return "Promising — worth a closer look before deciding.";
    default:
      return "Weak match against this role's requirements.";
  }
}

/** Deterministic avatar gradient from initials, matching the design's tinted tiles. */
export function avatarGradient(seed: string): string {
  const palettes = [
    "linear-gradient(135deg,#2F5BFF,#7C8BFF)",
    "linear-gradient(135deg,#0E9F6E,#5FD3A0)",
    "linear-gradient(135deg,#E0A500,#F4CE5E)",
    "linear-gradient(135deg,#E5544B,#F58A83)",
    "linear-gradient(135deg,#5B6072,#9CA3B0)",
    "linear-gradient(135deg,#22D3EE,#6E92FF)",
  ];
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return palettes[h % palettes.length];
}

export function initials(name: string | null | undefined): string {
  if (!name) return "··";
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "··";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
