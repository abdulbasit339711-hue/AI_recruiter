// src/app/admin/layout.tsx
import { ReactNode } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { AppBackground } from "@/components/layout/AppBackground";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <AppBackground />
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar />
          <main className="flex-1 px-4 py-6 sm:px-7 sm:py-8">
            <div className="mx-auto w-full max-w-[1200px]">{children}</div>
          </main>
        </div>
      </div>
    </>
  );
}
