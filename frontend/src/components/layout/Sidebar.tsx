// src/components/layout/Sidebar.tsx
"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGrid, Briefcase, Users, BarChart3 } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/admin/candidates", label: "Candidates", icon: LayoutGrid },
  { href: "/admin/jobs", label: "Jobs", icon: Briefcase },
  { href: "/admin/dashboard", label: "Insights", icon: BarChart3 },
] as const;

function BrandMark() {
  return (
    <div className="flex h-[34px] w-[34px] items-center justify-center rounded-[10px] bg-primary text-primary-foreground shadow-[0_8px_18px_-6px_var(--primary)]">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" />
        <path d="M12 12l8-4.5M12 12v9M12 12L4 7.5" />
      </svg>
    </div>
  );
}

/** Persistent left rail (lg+). On smaller screens the Topbar carries the nav. */
export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="glass-rail sticky top-0 hidden h-screen w-[236px] shrink-0 flex-col gap-1.5 p-[18px] lg:flex">
      <Link href="/admin/candidates" className="flex items-center gap-[11px] px-2 pb-5 pt-1">
        <BrandMark />
        <span className="font-display text-base font-bold tracking-tight text-heading">Recruiter</span>
      </Link>

      {NAV.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-[11px] rounded-xl px-3 py-[11px] text-sm transition-colors",
              active
                ? "bg-accent font-semibold text-accent-foreground"
                : "font-medium text-muted-foreground hover:bg-foreground/[0.04] hover:text-foreground"
            )}
          >
            <Icon className="h-[18px] w-[18px]" strokeWidth={1.9} />
            {label}
          </Link>
        );
      })}

      <div className="flex-1" />

      <div className="rounded-2xl border border-glass-border bg-foreground/[0.03] p-3.5">
        <p className="text-[13px] font-semibold text-heading">Need a hand?</p>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          Every score links to a plain&#8209;language explainer.
        </p>
      </div>
    </aside>
  );
}
