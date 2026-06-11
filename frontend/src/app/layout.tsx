// src/app/layout.tsx
import './globals.css';
import { Outfit } from 'next/font/google';
import { ReactNode } from 'react';
import { Providers } from '@/components/providers';

const outfit = Outfit({ 
  subsets: ['latin'],
  variable: '--font-body',
  weight: ['300', '400', '500', '600', '700', '800']
});

export const metadata = {
  title: 'AI Recruiter Leaderboard',
  description: 'Unified Candidate Parser & Multi-Job Semantic Scoring System',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${outfit.variable} font-sans`} suppressHydrationWarning>
      <body
        suppressHydrationWarning
        className="bg-background text-foreground min-h-screen flex flex-col antialiased selection:bg-primary/20"
      >
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}

