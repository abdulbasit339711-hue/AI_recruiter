// src/components/layout/Sidebar.tsx
"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Briefcase, Users } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/jobs", label: "Jobs", icon: Briefcase },
  { href: "/admin/candidates", label: "Candidates", icon: Users },
] as const;

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      className="flex h-screen w-60 shrink-0 flex-col"
      style={{
        background: "#04111B",
        borderRight: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      {/* Brand */}
      <div className="flex items-center gap-3 px-5 pb-4 pt-6">
        <div
          className="flex h-8 w-8 items-center justify-center rounded-lg font-bold text-white"
          style={{ background: "#1C99BF" }}
        >
          O
        </div>
        <span className="font-sans text-[15px] font-semibold text-heading">
          ZI Recruiter
        </span>
      </div>

      {/* Nav */}
      <nav className="flex flex-1 flex-col gap-1 px-3 pt-2">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "border-l-2 border-primary font-semibold text-primary"
                  : "text-muted-foreground hover:bg-white/5 hover:text-foreground"
              )}
              style={
                active
                  ? { background: "rgba(28,153,191,0.15)" }
                  : undefined
              }
            >
              <Icon className="h-[18px] w-[18px]" strokeWidth={1.8} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 pb-5 pt-3">
        <p
          className="font-sans text-[11px]"
          style={{ color: "#556070" }}
        >
          OZI Recruiter v1
        </p>
      </div>
    </aside>
  );
}
