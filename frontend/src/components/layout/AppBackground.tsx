// src/components/layout/AppBackground.tsx
// Fixed, theme-aware atmosphere (color mesh + grain) that sits behind all content.
// Pure CSS via tokens in globals.css — no JS, no scroll repaint cost.
export function AppBackground() {
  return <div className="app-atmosphere" aria-hidden="true" />;
}
