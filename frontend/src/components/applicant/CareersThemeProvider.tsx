"use client";

import { ReactNode } from "react";

// Parse a #rrggbb or #rgb hex string → [h°, s%, l%]
function hexToHsl(hex: string): [number, number, number] {
  const clean = hex.replace("#", "");
  const full = clean.length === 3
    ? clean.split("").map((c) => c + c).join("")
    : clean;
  const r = parseInt(full.slice(0, 2), 16) / 255;
  const g = parseInt(full.slice(2, 4), 16) / 255;
  const b = parseInt(full.slice(4, 6), 16) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const l = (max + min) / 2;
  if (max === min) return [0, 0, Math.round(l * 100)];
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h = 0;
  if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
  else if (max === g) h = ((b - r) / d + 2) / 6;
  else h = ((r - g) / d + 4) / 6;
  return [Math.round(h * 360), Math.round(s * 100), Math.round(l * 100)];
}

interface Props {
  color: string;   // brand hex e.g. "#1C99BF"
  children: ReactNode;
}

export function CareersThemeProvider({ color, children }: Props) {
  let h = 198, s = 74, l = 46; // fallback: OZI blue
  try {
    if (/^#[0-9a-fA-F]{3,6}$/.test(color)) {
      [h, s, l] = hexToHsl(color);
    }
  } catch { /* keep fallback */ }

  // Complementary hue for the secondary gradient blob
  const h2 = (h + 40) % 360;

  // Dark background: keep the hue, crush saturation + lightness
  const bgS = Math.round(s * 0.22);
  const bgL = 6;

  // Glass card surface
  const cardS = Math.round(s * 0.32);

  // Atmosphere blobs
  const atmoOpacity1 = 0.22;
  const atmoOpacity2 = 0.12;
  const atmoOpacity3 = 0.09;

  const css = `
.careers-theme {
  --brand-h: ${h};
  --brand-s: ${s}%;
  --brand-l: ${l}%;
}
/* Override dark-mode surface + atmosphere variables inside .careers-theme */
.dark .careers-theme,
.careers-theme {
  --background:    hsl(${h}, ${bgS}%, ${bgL}%);
  --glass-top:     hsla(${h}, ${cardS}%, 13%, 0.80);
  --glass-bottom:  hsla(${h}, ${Math.round(cardS * 0.7)}%, 7%, 0.65);
  --glass-border:  hsla(${h}, ${s}%, ${l}%, 0.16);
  --glass-inset:   hsla(${h}, ${s}%, ${l}%, 0.07);
  --glass-shadow:  0 24px 60px -28px rgba(0,0,0,0.72),
                   0 0 0 1px hsla(${h}, ${s}%, ${l}%, 0.09);
  --surface-card:  hsla(${h}, ${cardS}%, 10%, 0.72);
  --atmo:
    radial-gradient(900px 540px at 12% -6%,  hsla(${h},  ${s}%, ${l}%, ${atmoOpacity1}), transparent 58%),
    radial-gradient(640px 420px at 92%  4%,  hsla(${h2}, ${Math.round(s * 0.75)}%, ${Math.min(l + 12, 80)}%, ${atmoOpacity2}), transparent 54%),
    radial-gradient(720px 640px at 55% 112%, hsla(${h2}, ${Math.round(s * 0.6)}%,  ${l}%, ${atmoOpacity3}), transparent 62%);
}
/* Tint the grain layer's background so it blends with the new bg */
.careers-theme .app-atmosphere {
  background-color: hsl(${h}, ${bgS}%, ${bgL}%);
  background-image: var(--atmo);
}
  `.trim();

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: css }} />
      <div className="careers-theme">{children}</div>
    </>
  );
}
