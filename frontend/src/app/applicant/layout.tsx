import { ReactNode } from "react";
import Link from "next/link";
import { Briefcase } from "lucide-react";

/**
 * Applicant-facing ("Careers") layout — intentionally distinct from the HR admin
 * dashboard chrome: a clean branded header, no sidebar, no admin controls.
 */
export default function ApplicantLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-mesh">
      <header className="border-b border-white/10 bg-background/70 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Link href="/applicant" className="flex items-center gap-2 font-semibold">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary/15 text-primary">
              <Briefcase className="h-4 w-4" />
            </span>
            <span>AI Recruiter <span className="text-muted-foreground">Careers</span></span>
          </Link>
          <Link href="/applicant" className="text-sm text-muted-foreground hover:text-foreground">
            All openings
          </Link>
        </div>
      </header>
      <main className="flex-1">{children}</main>
      <footer className="border-t border-white/10 py-6 text-center text-xs text-muted-foreground">
        © AI Recruiter — Careers
      </footer>
    </div>
  );
}
