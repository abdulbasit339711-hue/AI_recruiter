// src/app/admin/layout.tsx
"use client";

import React from "react";
import { Header } from "@/components/layout/header";
import { ReactNode } from "react";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <Header />
      <main className="min-h-screen bg-mesh text-card-foreground">
        <div className="mx-auto max-w-7xl px-4 py-6">{children}</div>
      </main>
    </>
  );
}
