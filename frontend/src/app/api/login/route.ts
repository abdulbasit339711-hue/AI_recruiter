// Admin login: validates the shared admin token against the server-side
// ADMIN_API_TOKEN (constant-time) and, on success, sets an httpOnly cookie holding a
// short-lived SIGNED SESSION TOKEN — not the raw secret, so a cookie leak is no longer a
// full backend compromise. Per-IP rate limiting blunts brute-force. No DB, no users.

import { NextRequest, NextResponse } from "next/server";
import { mintSession, verifySession, safeEqual, SESSION_COOKIE, SESSION_MAX_AGE_S } from "@/lib/session";

const ADMIN_API_TOKEN = process.env.ADMIN_API_TOKEN || "";

// In-memory per-IP rate limit (best-effort; single-instance). Resets on the window.
const ATTEMPTS = new Map<string, { count: number; resetAt: number }>();
const MAX_ATTEMPTS = 8;
const WINDOW_MS = 5 * 60 * 1000;

function rateLimited(ip: string): boolean {
  const now = Date.now();
  const rec = ATTEMPTS.get(ip);
  if (!rec || now > rec.resetAt) {
    ATTEMPTS.set(ip, { count: 1, resetAt: now + WINDOW_MS });
    return false;
  }
  rec.count += 1;
  return rec.count > MAX_ATTEMPTS;
}

export async function POST(req: NextRequest): Promise<NextResponse> {
  if (!ADMIN_API_TOKEN) {
    return NextResponse.json({ ok: false, error: "Server auth not configured." }, { status: 503 });
  }
  const ip =
    req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    req.headers.get("x-real-ip") ||
    "local";
  if (rateLimited(ip)) {
    return NextResponse.json(
      { ok: false, error: "Too many attempts. Try again in a few minutes." },
      { status: 429 }
    );
  }

  const { token } = await req.json().catch(() => ({ token: "" }));
  if (typeof token !== "string" || !safeEqual(token, ADMIN_API_TOKEN)) {
    return NextResponse.json({ ok: false, error: "Invalid token." }, { status: 401 });
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, mintSession(), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_MAX_AGE_S,
  });
  return res;
}

export async function DELETE(): Promise<NextResponse> {
  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, "", { httpOnly: true, path: "/", maxAge: 0 });
  return res;
}

// Lets the client verify the current cookie is still a valid (signed, unexpired) session.
export async function GET(req: NextRequest): Promise<NextResponse> {
  return NextResponse.json({ ok: verifySession(req.cookies.get(SESSION_COOKIE)?.value) });
}
