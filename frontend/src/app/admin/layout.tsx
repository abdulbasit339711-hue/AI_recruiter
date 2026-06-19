// src/app/admin/layout.tsx
import { ReactNode } from 'react';
import { TopNav } from '@/components/layout/TopNav';
import { AppBackground } from '@/components/layout/AppBackground';

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <div style={{ minHeight: '100vh', background: '#04111B' }}>
      <AppBackground />
      <TopNav />
      <main className="relative z-10">
        {children}
      </main>
    </div>
  );
}
