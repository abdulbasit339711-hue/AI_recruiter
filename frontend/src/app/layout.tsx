// src/app/layout.tsx
import './globals.css';
import localFont from 'next/font/local';
import { ReactNode } from 'react';
import { Providers } from '@/components/providers';

const display = localFont({
  src: [
    { path: '../../public/fonts/Poppins-400.woff2', weight: '400' },
    { path: '../../public/fonts/Poppins-500.woff2', weight: '500' },
    { path: '../../public/fonts/Poppins-600.woff2', weight: '600' },
    { path: '../../public/fonts/Poppins-700.woff2', weight: '700' },
    { path: '../../public/fonts/Poppins-800.woff2', weight: '800' },
  ],
  variable: '--font-display',
  display: 'swap',
});

const sans = localFont({
  src: [
    { path: '../../public/fonts/Poppins-300.woff2', weight: '300' },
    { path: '../../public/fonts/Poppins-400.woff2', weight: '400' },
    { path: '../../public/fonts/Poppins-500.woff2', weight: '500' },
    { path: '../../public/fonts/Poppins-600.woff2', weight: '600' },
    { path: '../../public/fonts/Poppins-700.woff2', weight: '700' },
  ],
  variable: '--font-sans',
  display: 'swap',
});

const mono = localFont({
  src: [
    { path: '../../public/fonts/JetBrainsMono-400.woff2', weight: '400' },
  ],
  variable: '--font-mono',
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
