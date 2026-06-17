"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import { setHrActor } from "@/lib/actor";
import { AppBackground } from "@/components/layout/AppBackground";
import { FadeIn, Stagger, StaggerItem } from "@/components/ui/motion";

function LoginForm() {
  const [token, setToken] = useState("");
  const [actor, setActor] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const params = useSearchParams();
  // Only allow internal redirects (block open-redirect via ?next=//evil.com).
  const rawNext = params.get("next") || "/admin/dashboard";
  const next = rawNext.startsWith("/") && !rawNext.startsWith("//") ? rawNext : "/admin/dashboard";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (res.ok) {
        if (actor.trim()) setHrActor(actor);  // attribute audit-trail changes to this operator
        router.push(next);
        router.refresh();
      } else {
        const body = await res.json().catch(() => ({}));
        setError(body.error || "Login failed.");
      }
    } catch {
      setError("Could not reach the server.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <AppBackground />
      <main className="flex min-h-screen items-center justify-center px-4">
        <FadeIn y={20} className="w-full max-w-sm">
          <form
            onSubmit={submit}
            className="glass w-full space-y-5 rounded-2xl p-7"
          >
            <Stagger className="space-y-5" gap={0.07} delay={0.15}>
              <StaggerItem className="flex flex-col items-center gap-3 text-center">
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-[0_10px_22px_-8px_var(--primary)]">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" />
                    <path d="M12 12l8-4.5M12 12v9M12 12L4 7.5" />
                  </svg>
                </span>
                <div>
                  <h1 className="font-display text-xl font-bold text-heading">Admin sign in</h1>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Enter the admin access token to continue.
                  </p>
                </div>
              </StaggerItem>

              <StaggerItem className="space-y-1.5">
                <label htmlFor="login-token" className="block text-xs font-medium text-muted-foreground">
                  Admin token
                </label>
                <input
                  id="login-token"
                  type="password"
                  autoFocus
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="Admin token"
                  className="w-full rounded-lg border border-border bg-foreground/[0.03] px-3 py-2.5 text-sm outline-none transition focus:border-ring focus:ring-1 focus:ring-ring"
                />
              </StaggerItem>

              <StaggerItem className="space-y-1.5">
                <label htmlFor="login-actor" className="block text-xs font-medium text-muted-foreground">
                  Your email <span className="text-faint">(optional — for the audit trail)</span>
                </label>
                <input
                  id="login-actor"
                  type="email"
                  value={actor}
                  onChange={(e) => setActor(e.target.value)}
                  placeholder="you@company.com"
                  className="w-full rounded-lg border border-border bg-foreground/[0.03] px-3 py-2.5 text-sm outline-none transition focus:border-ring focus:ring-1 focus:ring-ring"
                />
              </StaggerItem>

              <StaggerItem className="space-y-3">
                {error && <p className="text-sm text-weak">{error}</p>}
                <button
                  type="submit"
                  disabled={loading || !token}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2.5 text-sm font-semibold text-primary-foreground shadow-[0_10px_24px_-10px_var(--primary)] transition hover:opacity-90 disabled:opacity-50"
                >
                  {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
                  {loading ? "Signing in…" : "Sign in"}
                </button>
              </StaggerItem>
            </Stagger>
          </form>
        </FadeIn>
      </main>
    </>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
