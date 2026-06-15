// src/app/admin/dashboard/page.tsx
"use client";

import React from "react";
import Link from "next/link";
import { Briefcase, Users, ArrowRight } from "lucide-react";
import { ScoreVisualization } from "@/components/admin/ScoreVisualization";
import { GlassCard } from "@/components/ui/GlassCard";
import { Reveal } from "@/components/ui/Reveal";

const SHORTCUTS = [
  { href: "/admin/jobs", label: "Jobs", desc: "Manage openings", icon: Briefcase },
  { href: "/admin/candidates", label: "Candidates", desc: "Open leaderboard", icon: Users },
] as const;

export default function AdminDashboardPage() {
  return (
    <div className="space-y-7">
      <div className="flex flex-col gap-1.5">
        <p className="font-mono text-xs uppercase tracking-[0.06em] text-muted-foreground">Insights</p>
        <h1 className="font-display text-[30px] font-bold leading-none tracking-tight text-heading">Screening Overview</h1>
        <p className="text-sm text-muted-foreground">Monitor throughput and jump into the active work queues.</p>
      </div>

      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
        {SHORTCUTS.map(({ href, label, desc, icon: Icon }, i) => (
          <Reveal key={href} index={i}>
            <GlassCard variant="tile" hover className="p-5">
              <Link href={href} className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-heading">{label}</p>
                  <p className="mt-1 flex items-center gap-1 text-sm text-primary-strong">
                    {desc}
                    <ArrowRight className="h-3.5 w-3.5" />
                  </p>
                </div>
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-accent-foreground">
                  <Icon className="h-5 w-5" strokeWidth={1.9} />
                </span>
              </Link>
            </GlassCard>
          </Reveal>
        ))}
      </div>

      <ScoreVisualization />
    </div>
  );
}
