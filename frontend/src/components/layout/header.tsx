"use client";

import React from "react";
import { BriefcaseBusiness, LayoutDashboard, ListChecks, Moon, Sun, UsersRound } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";

export function Header() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  const pathname = usePathname();
  React.useEffect(() => setMounted(true), []);
  const links = [
    { href: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/admin/jobs", label: "Jobs", icon: ListChecks },
    { href: "/admin/candidates", label: "Candidates", icon: UsersRound },
  ];

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-background/95 backdrop-blur">
      <div className="mx-auto flex min-h-16 max-w-7xl flex-col gap-3 px-4 py-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md border border-sky-400/20 bg-sky-400/10">
            <BriefcaseBusiness className="h-5 w-5 text-sky-300" />
          </div>
          <div>
            <p className="text-sm font-semibold leading-none">AI Recruiter</p>
            <p className="mt-1 text-xs text-muted-foreground">Screening operations</p>
          </div>
        </div>
        <nav className="flex flex-wrap items-center gap-2">
          {links.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || pathname?.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium transition-colors ${
                  active
                    ? "bg-sky-400/12 text-sky-200"
                    : "text-muted-foreground hover:bg-white/[0.07] hover:text-foreground"
                }`}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-white/10 bg-white/[0.03] text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground"
            title="Toggle theme"
          >
            {mounted && (resolvedTheme === "dark" ? (
              <Sun className="h-4 w-4 text-amber-300" />
            ) : (
              <Moon className="h-4 w-4" />
            ))}
          </button>
        </nav>
      </div>
    </header>
  );
}
