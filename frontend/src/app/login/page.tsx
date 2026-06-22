"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { setHrActor } from "@/lib/actor";
import { AppBackground } from "@/components/layout/AppBackground";
import { GlassCard } from "@/components/ui/GlassCard";
import { FadeIn, Stagger, StaggerItem } from "@/components/ui/motion";

function LoginForm() {
  const [token, setToken] = useState("");
  const [actor, setActor] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showToken, setShowToken] = useState(false);
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
        if (actor.trim()) setHrActor(actor); // attribute audit-trail changes to this operator
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

  const inputClass =
    "w-full rounded-xl bg-card border border-border px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-colors";

  return (
    <>
      <AppBackground />
      <main className="flex min-h-screen items-center justify-center bg-background px-4">
        <FadeIn y={24} className="w-full max-w-sm mx-4">
          <GlassCard variant="panel" className="w-full p-8">
            <form onSubmit={submit}>
              <Stagger className="space-y-6" gap={0.08} delay={0.12}>

                {/* Logo + branding */}
                <StaggerItem className="flex flex-col items-center gap-4 text-center">
                  <div
                    className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary text-white font-bold text-xl select-none"
                    style={{ boxShadow: "0 12px 28px -8px var(--primary)" }}
                    aria-hidden="true"
                  >
                    O
                  </div>
                  <div>
                    <h1 className="text-xl font-bold text-heading tracking-tight">
                      OZI Recruiter
                    </h1>
                    <p className="mt-1 text-sm text-muted-foreground">
                      AI-powered hiring platform
                    </p>
                  </div>
                </StaggerItem>

                {/* Fields */}
                <StaggerItem className="space-y-4">
                  {/* Access token */}
                  <div className="space-y-1.5">
                    <label
                      htmlFor="login-token"
                      className="block text-xs font-medium text-muted-foreground"
                    >
                      Access token
                    </label>
                    <div className="relative">
                      <input
                        id="login-token"
                        type={showToken ? "text" : "password"}
                        autoFocus
                        autoComplete="current-password"
                        value={token}
                        onChange={(e) => setToken(e.target.value)}
                        placeholder="Enter your access token"
                        className={inputClass + " pr-10"}
                      />
                      <button
                        type="button"
                        onClick={() => setShowToken((v) => !v)}
                        className="absolute inset-y-0 right-3 flex items-center text-muted-foreground hover:text-foreground transition-colors"
                        aria-label={showToken ? "Hide token" : "Show token"}
                        tabIndex={-1}
                      >
                        {showToken ? (
                          <EyeOff className="h-4 w-4" aria-hidden />
                        ) : (
                          <Eye className="h-4 w-4" aria-hidden />
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Email / actor */}
                  <div className="space-y-1.5">
                    <label
                      htmlFor="login-actor"
                      className="block text-xs font-medium text-muted-foreground"
                    >
                      Your email{" "}
                      <span className="opacity-50">(optional — audit trail)</span>
                    </label>
                    <input
                      id="login-actor"
                      type="email"
                      autoComplete="email"
                      value={actor}
                      onChange={(e) => setActor(e.target.value)}
                      placeholder="you@company.com"
                      className={inputClass}
                    />
                  </div>
                </StaggerItem>

                {/* Error + submit */}
                <StaggerItem className="space-y-3">
                  {error && (
                    <p
                      role="alert"
                      className="rounded-lg border border-weak/30 bg-weak/10 px-3 py-2 text-sm text-weak"
                    >
                      {error}
                    </p>
                  )}
                  <button
                    type="submit"
                    disabled={loading || !token}
                    className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                    style={{ boxShadow: "0 10px 24px -10px var(--primary)" }}
                  >
                    {loading && (
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                    )}
                    {loading ? "Signing in…" : "Sign in"}
                  </button>
                </StaggerItem>

              </Stagger>
            </form>
          </GlassCard>
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
