// src/components/layout/Topbar.tsx
"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGrid, Briefcase, BarChart3 } from "lucide-react";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/admin/candidates", label: "Candidates", icon: LayoutGrid },
  { href: "/admin/jobs", label: "Jobs", icon: Briefcase },
  { href: "/admin/dashboard", label: "Insights", icon: BarChart3 },
] as const;

/** Sticky glass top bar. Carries the primary nav on screens below `lg`. */
export function Topbar() {
  const pathname = usePathname();
  return (
    <header className="glass-rail sticky top-0 z-40 flex items-center gap-3 px-5 py-3 sm:px-7">
      {/* Mobile brand */}
      <Link href="/admin/candidates" className="flex items-center gap-2.5 lg:hidden">
        <span className="flex h-8 w-8 items-center justify-center rounded-[9px] bg-primary text-primary-foreground">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" />
            <path d="M12 12l8-4.5M12 12v9M12 12L4 7.5" />
          </svg>
        </span>
        <span className="font-display text-[15px] font-bold tracking-tight text-heading">Recruiter</span>
      </Link>

      {/* Mobile nav */}
      <nav className="flex items-center gap-1 overflow-x-auto lg:hidden">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[13px] font-medium transition-colors",
                active ? "bg-accent text-accent-foreground" : "text-muted-foreground"
              )}
            >
              <Icon className="h-4 w-4" strokeWidth={1.9} />
              <span className="hidden sm:inline">{label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="flex-1" />

      <ThemeToggle />
      <Link
        href="/login"
        title="Account"
        className="flex h-9 w-9 items-center justify-center rounded-full bg-[linear-gradient(135deg,var(--primary),#22d3ee)] text-[13px] font-semibold text-white"
      >
        HR
      </Link>
    </header>
  );
}
