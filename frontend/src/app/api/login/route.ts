// Login: validates the provided token against ADMIN_API_TOKEN (admin role) or
// HR_API_TOKEN (hr role). On success, sets an httpOnly signed SESSION TOKEN cookie
// (not the raw secret) plus a readable user_role cookie for client-side UI gating.
// Per-IP rate limiting blunts brute-force. No DB, no users.

import { NextRequest, NextResponse } from "next/server";
import {
  mintSession,
  verifySession,
  safeEqual,
  SESSION_COOKIE,
  ROLE_COOKIE,
  SESSION_MAX_AGE_S,
  type SessionRole,
} from "@/lib/session";

const ADMIN_API_TOKEN = process.env.ADMIN_API_TOKEN || "";
const HR_API_TOKEN = process.env.HR_API_TOKEN || "";

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

function resolveRole(token: string): SessionRole | null {
  if (ADMIN_API_TOKEN && safeEqual(token, ADMIN_API_TOKEN)) return "admin";
  if (HR_API_TOKEN && safeEqual(token, HR_API_TOKEN)) return "hr";
  return null;
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
  if (typeof token !== "string") {
    return NextResponse.json({ ok: false, error: "Invalid token." }, { status: 401 });
  }

  const role = resolveRole(token);
  if (!role) {
    return NextResponse.json({ ok: false, error: "Invalid token." }, { status: 401 });
  }

  const isSecure = process.env.NODE_ENV === "production";
  const res = NextResponse.json({ ok: true, role });
  res.cookies.set(SESSION_COOKIE, mintSession(role), {
    httpOnly: true,
    sameSite: "lax",
    secure: isSecure,
    path: "/",
    maxAge: SESSION_MAX_AGE_S,
  });
  // Non-httpOnly so client JS can read it for UI gating. Not a secret — enforcement
  // is server-side in the proxy. Cleared together with the session on logout.
  res.cookies.set(ROLE_COOKIE, role, {
    httpOnly: false,
    sameSite: "lax",
    secure: isSecure,
    path: "/",
    maxAge: SESSION_MAX_AGE_S,
  });
  return res;
}

export async function DELETE(): Promise<NextResponse> {
  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, "", { httpOnly: true, path: "/", maxAge: 0 });
  res.cookies.set(ROLE_COOKIE, "", { httpOnly: false, path: "/", maxAge: 0 });
  return res;
}

// Lets the client verify the current cookie is still a valid (signed, unexpired) session.
export async function GET(req: NextRequest): Promise<NextResponse> {
  return NextResponse.json({ ok: verifySession(req.cookies.get(SESSION_COOKIE)?.value) });
}
