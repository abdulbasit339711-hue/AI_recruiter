"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Bell, Briefcase, LayoutDashboard, Users } from "lucide-react";

const NAV_ITEMS = [
  { to: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/admin/jobs", label: "Jobs", icon: Briefcase },
  { to: "/admin/candidates", label: "Candidates", icon: Users },
];

export function TopNav() {
  const pathname = usePathname();

  return (
    <header
      className="sticky top-0 z-40 border-b border-white/[0.06] backdrop-blur-xl"
      style={{ background: "rgba(4,17,27,0.85)" }}
    >
      <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Logo */}
        <Link href="/admin/dashboard" className="flex items-center gap-2.5 shrink-0">
          <svg viewBox="0 0 36 36" className="h-8 w-8">
            <circle
              cx="18" cy="18" r="14"
              fill="none" stroke="#1C99BF" strokeWidth="2.5" opacity="0.25"
            />
            <motion.circle
              cx="18" cy="18" r="14"
              fill="none" stroke="#1C99BF" strokeWidth="2.5"
              strokeLinecap="round"
              strokeDasharray="44 88"
              transform="rotate(-90 18 18)"
              initial={{ strokeDashoffset: 88 }}
              animate={{ strokeDashoffset: 0 }}
              transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1] }}
              style={{ filter: "drop-shadow(0 0 4px rgba(28,153,191,0.6))" }}
            />
          </svg>
          <div>
            <span className="font-mono text-base font-bold" style={{ color: "#1C99BF" }}>OZI</span>
            <span className="ml-0.5 font-mono text-base font-bold text-white/60"> Recruiter</span>
          </div>
        </Link>

        {/* Center nav */}
        <nav className="hidden md:flex items-center gap-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = pathname.startsWith(item.to);
            return (
              <Link
                key={item.to}
                href={item.to}
                className="relative flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
                style={{ color: isActive ? "#1C99BF" : "#9CA3B0" }}
              >
                {isActive && (
                  <motion.div
                    layoutId="nav-active"
                    className="-z-10 absolute inset-0 rounded-lg"
                    style={{ background: "rgba(28,153,191,0.1)" }}
                    transition={{ type: "spring", duration: 0.4 }}
                  />
                )}
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Right side */}
        <div className="flex items-center gap-2">
          {/* Bell */}
          <button className="relative rounded-lg p-2 text-muted-foreground hover:text-heading transition-colors">
            <Bell className="h-5 w-5" />
            <span
              className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full"
              style={{ background: "#1C99BF", boxShadow: "0 0 8px #1C99BF" }}
            />
          </button>

          {/* Avatar pill */}
          <div
            className="flex items-center gap-2.5 rounded-full border border-white/[0.08] py-1 pl-1 pr-3"
            style={{ background: "rgba(8,34,52,0.6)" }}
          >
            <div
              className="flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-white"
              style={{ background: "linear-gradient(135deg, #1C99BF, #3DAFCC)" }}
            >
              AD
            </div>
            <div className="hidden sm:block">
              <p className="text-xs font-semibold text-heading leading-none">Admin</p>
              <p className="mt-0.5 text-[10px] text-muted-foreground">Recruiter</p>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile bottom nav */}
      <div className="flex items-center justify-around border-t border-white/[0.04] px-2 py-1 md:hidden">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = pathname.startsWith(item.to);
          return (
            <Link
              key={item.to}
              href={item.to}
              className="flex flex-col items-center gap-1 px-4 py-2 text-[10px] font-medium transition-colors"
              style={{ color: isActive ? "#1C99BF" : "#9CA3B0" }}
            >
              <Icon className="h-5 w-5" />
              {item.label}
            </Link>
          );
        })}
      </div>
    </header>
  );
}
