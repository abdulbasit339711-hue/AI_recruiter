// src/app/layout.tsx
import './globals.css';
import { Poppins, JetBrains_Mono } from 'next/font/google';
import { ReactNode } from 'react';
import { Providers } from '@/components/providers';

// OZI Group — Poppins for both display and body
const display = Poppins({
  subsets: ['latin'],
  variable: '--font-display',
  weight: ['400', '500', '600', '700', '800'],
  display: 'swap',
});

const sans = Poppins({
  subsets: ['latin'],
  variable: '--font-sans',
  weight: ['300', '400', '500', '600', '700'],
  display: 'swap',
});

// OZI Group — JetBrains Mono for code / scores / numbers
const mono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  weight: ['400', '500', '600'],
  display: 'swap',
});

export const metadata = {
  title: 'OZI Recruiter',
  description: 'AI-powered hiring — scoring, aptitude, and interviews in one place.',
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
