// src/app/admin/layout.tsx
import { ReactNode } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { AppBackground } from "@/components/layout/AppBackground";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="relative flex-1 overflow-y-auto">
        <AppBackground />
        <main className="relative px-6 py-8">
          <div className="mx-auto w-full max-w-[1200px]">{children}</div>
        </main>
      </div>
    </div>
  );
}
