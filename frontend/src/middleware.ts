// Gate the admin dashboard behind the admin_session cookie. The authoritative
// security check is in the backend proxy (src/app/api/admin/[...path]/route.ts);
// this just keeps unauthenticated users out of the admin UI shell and bounces
// them to /login. Applicant/interview pages are intentionally not matched.

import { NextRequest, NextResponse } from "next/server";

export function middleware(req: NextRequest) {
  const expected = process.env.ADMIN_API_TOKEN || "";
  const cookie = req.cookies.get("admin_session")?.value;
  if (!expected || cookie !== expected) {
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
