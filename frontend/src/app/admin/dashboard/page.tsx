// src/app/admin/dashboard/page.tsx
"use client";

import React from "react";
import { ScoreVisualization } from "@/components/admin/ScoreVisualization";
import { Card, CardContent } from "@/components/ui/card";
import Link from "next/link";
import { ListChecks, UsersRound } from "lucide-react";

export default function AdminDashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Admin Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">Monitor screening throughput and jump into the active work queues.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardContent className="flex items-center justify-between gap-4 p-4">
            <div>
              <p className="text-sm font-medium">Jobs</p>
              <Link href="/admin/jobs" className="mt-1 block text-sm text-sky-200 hover:underline">Manage openings</Link>
            </div>
            <ListChecks className="h-5 w-5 text-sky-300" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center justify-between gap-4 p-4">
            <div>
              <p className="text-sm font-medium">Candidates</p>
              <Link href="/admin/candidates" className="mt-1 block text-sm text-sky-200 hover:underline">Open leaderboard</Link>
            </div>
            <UsersRound className="h-5 w-5 text-emerald-300" />
          </CardContent>
        </Card>
      </div>

      <ScoreVisualization />
    </div>
  );
}
