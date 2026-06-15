// src/components/ui/ThemeToggle.tsx
"use client";

import * as React from "react";
import { useTheme } from "next-themes";
import { Sun, Moon } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Segmented light/dark toggle. Light is the default base; this is the opt-in.
 * Mirrors the design's pill control in the top bar.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  const current = (mounted ? theme ?? resolvedTheme : "light") ?? "light";

  return (
    <div
      className={cn(
        "inline-flex items-center gap-0.5 rounded-xl border p-1 glass-rail",
        className
      )}
      role="group"
      aria-label="Color theme"
    >
      <button
        type="button"
        aria-pressed={current === "light"}
        aria-label="Light theme"
        onClick={() => setTheme("light")}
        className={cn(
          "flex h-7 w-8 items-center justify-center rounded-lg transition-colors",
          current === "light"
            ? "bg-primary text-primary-foreground"
            : "text-muted-foreground hover:text-foreground"
        )}
      >
        <Sun className="h-[15px] w-[15px]" />
      </button>
      <button
        type="button"
        aria-pressed={current === "dark"}
        aria-label="Dark theme"
        onClick={() => setTheme("dark")}
        className={cn(
          "flex h-7 w-8 items-center justify-center rounded-lg transition-colors",
          current === "dark"
            ? "bg-primary text-primary-foreground"
            : "text-muted-foreground hover:text-foreground"
        )}
      >
        <Moon className="h-[15px] w-[15px]" />
      </button>
    </div>
  );
}
