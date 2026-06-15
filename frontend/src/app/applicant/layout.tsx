import { ReactNode } from "react";
import Link from "next/link";
import { AppBackground } from "@/components/layout/AppBackground";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

/**
 * Applicant-facing ("Careers") layout — intentionally distinct from the HR admin
 * dashboard chrome: a clean branded header, no sidebar, no admin controls.
 */
export default function ApplicantLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <AppBackground />
      <div className="flex min-h-screen flex-col">
        <header className="glass-rail sticky top-0 z-40">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
            <Link href="/applicant" className="flex items-center gap-2.5 font-semibold">
              <span className="flex h-8 w-8 items-center justify-center rounded-[9px] bg-primary text-primary-foreground">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" />
                  <path d="M12 12l8-4.5M12 12v9M12 12L4 7.5" />
                </svg>
              </span>
              <span className="font-display tracking-tight text-heading">
                AI Recruiter <span className="font-sans font-normal text-muted-foreground">Careers</span>
              </span>
            </Link>
            <div className="flex items-center gap-3">
              <Link href="/applicant" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
                All openings
              </Link>
              <ThemeToggle />
            </div>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-border py-6 text-center text-xs text-muted-foreground">
          © AI Recruiter — Careers
        </footer>
      </div>
    </>
  );
}
