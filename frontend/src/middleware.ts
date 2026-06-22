// Gate the admin dashboard shell behind the admin_session cookie. This runs on the
// Edge runtime (no node:crypto / Buffer), so it only does a cheap, crypto-FREE check:
// the cookie must be present and not expired. The AUTHORITATIVE signature verification
// happens in the Node-runtime proxy (src/app/api/admin/[...path]/route.ts), which every
// data call goes through — a forged-but-unsigned cookie gets past here but every API
// call 401s, so the dashboard is empty/unusable.

import { NextRequest, NextResponse } from "next/server";

function notExpired(token?: string): boolean {
  if (!token) return false;
  const body = token.split(".")[0];
  if (!body) return false;
  try {
    // base64url -> base64 -> JSON (atob is available on the Edge runtime; Buffer is not).
    const json = JSON.parse(atob(body.replace(/-/g, "+").replace(/_/g, "/")));
    return typeof json.exp === "number" && Date.now() < json.exp;
  } catch {
    return false;
  }
}

export function middleware(req: NextRequest) {
  if (!notExpired(req.cookies.get("admin_session")?.value)) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", req.nextUrl.pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/admin/:path*"],
};
