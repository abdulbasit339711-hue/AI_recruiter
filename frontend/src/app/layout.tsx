// src/app/layout.tsx
import './globals.css';
import { Bricolage_Grotesque, Geist, Geist_Mono } from 'next/font/google';
import { ReactNode } from 'react';
import { Providers } from '@/components/providers';

// Display / headings — warm, characterful
const display = Bricolage_Grotesque({
  subsets: ['latin'],
  variable: '--font-display',
  weight: ['400', '500', '600', '700', '800'],
  display: 'swap',
});

// Body / UI — clean, highly legible
const sans = Geist({
  subsets: ['latin'],
  variable: '--font-sans',
  weight: ['300', '400', '500', '600', '700'],
  display: 'swap',
});

// Numbers / scores / timers — tabular
const mono = Geist_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  weight: ['400', '500', '600'],
  display: 'swap',
});

export const metadata = {
  title: 'AI-Recruiter',
  description: 'A calm, premium hiring surface — scoring, aptitude, and interviews in one place.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="en"
      className={`${display.variable} ${sans.variable} ${mono.variable}`}
      suppressHydrationWarning
    >
      <body
        suppressHydrationWarning
        className="bg-background text-foreground min-h-screen flex flex-col antialiased font-sans selection:bg-primary/20"
      >
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
