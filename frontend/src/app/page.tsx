"use client";

import * as React from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-mesh p-8 text-center">
      <h1 className="mb-4 text-4xl font-semibold">AI Recruiter</h1>
      <p className="mb-8 max-w-prose text-muted-foreground">
        Manage job openings, upload candidate resumes, and review screening results.
      </p>
      <Link href="/admin/dashboard">
        <Button size="lg">Go to Admin Panel</Button>
      </Link>
    </main>
  );
}
