// src/app/admin/page.tsx
"use client";

import * as React from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function AdminPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-start bg-gradient-to-b from-gray-900 to-gray-800 p-8 pt-16">
      <h1 className="mb-6 text-3xl font-bold text-white">Admin Panel</h1>
      <div className="flex flex-col gap-4">
        <Link href="/admin/jobs" legacyBehavior passHref>
          <Button size="lg">Manage Jobs</Button>
        </Link>
        <Link href="/admin/candidates" legacyBehavior passHref>
          <Button size="lg">View Candidates</Button>
        </Link>
        <Link href="/" legacyBehavior passHref>
          <Button variant="outline" size="lg">Back to Home</Button>
        </Link>
      </div>
    </main>
  );
}
