// Minimal admin login: validates the shared token against the server-side
// ADMIN_API_TOKEN and, on success, sets an httpOnly cookie that gates the admin
// dashboard and the backend proxy. No DB, no users — just the shared secret.

import { NextRequest, NextResponse } from "next/server";

const ADMIN_API_TOKEN = process.env.ADMIN_API_TOKEN || "";

export async function POST(req: NextRequest): Promise<NextResponse> {
  const { token } = await req.json().catch(() => ({ token: "" }));
  if (!ADMIN_API_TOKEN) {
    return NextResponse.json({ ok: false, error: "Server auth not configured." }, { status: 503 });
  }
  if (typeof token !== "string" || token !== ADMIN_API_TOKEN) {
    return NextResponse.json({ ok: false, error: "Invalid token." }, { status: 401 });
  }
  const res = NextResponse.json({ ok: true });
  res.cookies.set("admin_session", token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 8, // 8 hours
  });
  return res;
}

export async function DELETE(): Promise<NextResponse> {
  const res = NextResponse.json({ ok: true });
  res.cookies.set("admin_session", "", { httpOnly: true, path: "/", maxAge: 0 });
  return res;
}
