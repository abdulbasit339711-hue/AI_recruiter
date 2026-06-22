import { ReactNode } from "react";
import Link from "next/link";
import { AppBackground } from "@/components/layout/AppBackground";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

const ORG_NAME = process.env.NEXT_PUBLIC_ORG_NAME || "Careers";
const ORG_COLOR = process.env.NEXT_PUBLIC_ORG_COLOR || "#1C99BF";
const ORG_LOGO_URL = process.env.NEXT_PUBLIC_ORG_LOGO_URL || "";

// Derive a 1-2 char monogram from the org name as fallback logo.
function monogram(name: string): string {
  const words = name.trim().split(/\s+/);
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

export default function ApplicantLayout({ children }: { children: ReactNode }) {
  const mono = monogram(ORG_NAME);

  return (
    <>
      <AppBackground />
      <div className="flex min-h-screen flex-col">
        <header className="glass-rail sticky top-0 z-40">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
            <Link href="/applicant" className="flex items-center gap-2.5 font-semibold">
              {/* Logo: image if provided, else coloured monogram */}
              {ORG_LOGO_URL ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={ORG_LOGO_URL}
                  alt={ORG_NAME}
                  className="h-8 w-8 rounded-[9px] object-contain"
                />
              ) : (
                <span
                  className="flex h-8 w-8 items-center justify-center rounded-[9px] text-sm font-bold text-white select-none"
                  style={{ background: ORG_COLOR }}
                >
                  {mono}
                </span>
              )}
              <span className="font-display tracking-tight text-heading">
                {ORG_NAME}{" "}
                <span className="font-sans font-normal text-muted-foreground">Careers</span>
              </span>
            </Link>

            <div className="flex items-center gap-3">
              <Link
                href="/applicant"
                className="text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                All openings
              </Link>
              <ThemeToggle />
            </div>
          </div>
        </header>

        <main className="flex-1">{children}</main>

        <footer className="border-t border-border py-6 text-center text-xs text-muted-foreground">
          © {ORG_NAME} — Careers
        </footer>
      </div>
    </>
  );
}
