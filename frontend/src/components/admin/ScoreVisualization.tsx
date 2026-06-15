// src/components/admin/ScoreVisualization.tsx
"use client";

import React from "react";
import { useMetrics } from "@/hooks/useMetrics";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { TrendingUp, Clock, CheckCircle, XCircle, Users, Loader2 } from "lucide-react";
import { motion } from "framer-motion";

export const ScoreVisualization: React.FC = () => {
  const { data: metrics, isLoading } = useMetrics();

  const container = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.1 } },
  };
  const item = {
    hidden: { opacity: 0, y: 10 },
    visible: { opacity: 1, y: 0 },
  };

  if (isLoading || !metrics) {
    return (
      <motion.div
        className="flex items-center justify-center h-64"
        initial="hidden"
        animate="visible"
        variants={item}
      >
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </motion.div>
    );
  }

  const distribution = [
    { name: "Pending", value: metrics.pendingCount },
    { name: "Processed", value: metrics.processedCount },
    { name: "Failed", value: metrics.failedCount },
  ];
  const maxDistribution = Math.max(...distribution.map((item) => item.value), 1);

  return (
    <motion.div className="space-y-6" initial="hidden" animate="visible" variants={container}>
      <div>
        <h2 className="text-lg font-semibold">Pipeline Metrics</h2>
        <p className="mt-1 text-sm text-muted-foreground">Counts include current and legacy statuses.</p>
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3 xl:grid-cols-6">
        <Card className="flex flex-col items-center p-4">
          <Users className="h-6 w-6 text-indigo-500 mb-2" />
          <CardHeader className="p-0"><CardTitle className="text-sm font-medium">Jobs</CardTitle></CardHeader>
          <CardContent className="p-0 text-lg font-semibold">{metrics.totalJobs}</CardContent>
        </Card>
        <Card className="flex flex-col items-center p-4">
          <Users className="h-6 w-6 text-indigo-500 mb-2" />
          <CardHeader className="p-0"><CardTitle className="text-sm font-medium">Candidates</CardTitle></CardHeader>
          <CardContent className="p-0 text-lg font-semibold">{metrics.totalCandidates}</CardContent>
        </Card>
        <Card className="flex flex-col items-center p-4">
          <TrendingUp className="h-6 w-6 text-emerald-500 mb-2" />
          <CardHeader className="p-0"><CardTitle className="text-sm font-medium">Avg Score</CardTitle></CardHeader>
          <CardContent className="p-0 text-lg font-semibold">{metrics.avgScore.toFixed(1)}</CardContent>
        </Card>
        <Card className="flex flex-col items-center p-4">
          <Clock className="h-6 w-6 text-yellow-500 mb-2" />
          <CardHeader className="p-0"><CardTitle className="text-sm font-medium">Pending</CardTitle></CardHeader>
          <CardContent className="p-0 text-lg font-semibold">{metrics.pendingCount}</CardContent>
        </Card>
        <Card className="flex flex-col items-center p-4">
          <CheckCircle className="h-6 w-6 text-green-500 mb-2" />
          <CardHeader className="p-0"><CardTitle className="text-sm font-medium">Processed</CardTitle></CardHeader>
          <CardContent className="p-0 text-lg font-semibold">{metrics.processedCount}</CardContent>
        </Card>
        <Card className="flex flex-col items-center p-4">
          <XCircle className="h-6 w-6 text-red-500 mb-2" />
          <CardHeader className="p-0"><CardTitle className="text-sm font-medium">Failed</CardTitle></CardHeader>
          <CardContent className="p-0 text-lg font-semibold">{metrics.failedCount}</CardContent>
        </Card>
      </div>
      <div className="glass space-y-4 rounded-2xl p-5">
        <h3 className="text-sm font-semibold text-heading">Status Distribution</h3>
        {distribution.map((entry) => (
          <div key={entry.name} className="grid grid-cols-[88px_1fr_48px] items-center gap-3 text-sm">
            <span className="text-muted-foreground">{entry.name}</span>
            <div className="h-3 overflow-hidden rounded-full bg-foreground/10">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${(entry.value / maxDistribution) * 100}%` }}
              />
            </div>
            <span className="text-right font-medium">{entry.value}</span>
          </div>
        ))}
      </div>
    </motion.div>
  );
};
