import { ReactNode } from "react";
import Link from "next/link";
import { AppBackground } from "@/components/layout/AppBackground";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { CareersThemeProvider } from "@/components/applicant/CareersThemeProvider";

interface Props {
  children: ReactNode;
  params: Promise<{ orgSlug: string }>;
}

interface OrgBranding {
  name: string;
  primary_color: string;
  logo_url: string | null;
  tagline: string | null;
}

function monogram(name: string): string {
  const words = name.trim().split(/\s+/);
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

async function fetchOrg(slug: string): Promise<OrgBranding | null> {
  try {
    const base = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
    const token = process.env.ADMIN_API_TOKEN || "";
    const res = await fetch(`${base}/orgs/${slug}`, {
      headers: token ? { authorization: `Bearer ${token}` } : {},
      next: { revalidate: 60 },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function CareersLayout({ children, params }: Props) {
  const { orgSlug } = await params;
  const org = await fetchOrg(orgSlug);

  const name = org?.name || orgSlug;
  const color = org?.primary_color || "#1C99BF";
  const logoUrl = org?.logo_url || "";
  const mono = monogram(name);

  return (
    <CareersThemeProvider color={color}>
      <AppBackground />
      <div className="flex min-h-screen flex-col">
        <header className="glass-rail sticky top-0 z-40">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
            <Link href={`/careers/${orgSlug}`} className="flex items-center gap-2.5 font-semibold">
              {logoUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={logoUrl} alt={name} className="h-8 w-8 rounded-[9px] object-contain" />
              ) : (
                <span
                  className="flex h-8 w-8 items-center justify-center rounded-[9px] text-sm font-bold text-white select-none"
                  style={{ background: color }}
                >
                  {mono}
                </span>
              )}
              <span className="font-display tracking-tight text-heading">
                {name}{" "}
                <span className="font-sans font-normal text-muted-foreground">Careers</span>
              </span>
            </Link>

            <div className="flex items-center gap-3">
              <Link
                href={`/careers/${orgSlug}`}
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
          © {name} — Careers
        </footer>
      </div>
    </CareersThemeProvider>
  );
}
