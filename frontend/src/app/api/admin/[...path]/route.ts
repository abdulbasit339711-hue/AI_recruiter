// Server-side proxy to the FastAPI backend.
//
// Why this exists: the backend now requires an admin bearer token. We keep that
// token on the SERVER only (BACKEND/ADMIN_API_TOKEN env, never NEXT_PUBLIC) and
// inject it here, so it is never shipped to the browser. The browser talks only
// to this same-origin proxy.
//
// Access model:
//   - A small public allowlist (view one job, submit a resume) is forwarded for
//     anyone — this is the candidate apply flow.
//   - Everything else requires the `admin_session` cookie (set at /login), so the
//     proxy is not an open relay.

import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND_URL = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const ADMIN_API_TOKEN = process.env.ADMIN_API_TOKEN || "";

function isPublic(method: string, path: string): boolean {
  if (method === "GET" && path === "jobs") return true; // careers listing
  if (method === "GET" && /^jobs\/\d+$/.test(path)) return true; // view one job
  if (method === "GET" && path === "iq-test") return true; // fetch pre-application IQ test
  if (method === "POST" && path === "iq-test/submit") return true; // submit IQ answers
  if (method === "POST" && path === "upload") return true; // submit a resume
  return false;
}

async function handle(
  req: NextRequest,
  ctx: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const { path: parts } = await ctx.params;
  const path = (parts || []).join("/");
  const method = req.method;

  if (!isPublic(method, path)) {
    const cookie = req.cookies.get("admin_session")?.value;
    if (!ADMIN_API_TOKEN || cookie !== ADMIN_API_TOKEN) {
      return NextResponse.json({ detail: "Not authenticated." }, { status: 401 });
    }
  }

  const headers = new Headers();
  const ct = req.headers.get("content-type");
  if (ct) headers.set("content-type", ct);
  const accept = req.headers.get("accept");
  if (accept) headers.set("accept", accept);
  if (ADMIN_API_TOKEN) headers.set("authorization", `Bearer ${ADMIN_API_TOKEN}`);

  const init: RequestInit & { duplex?: "half" } = { method, headers, redirect: "manual" };
  if (method !== "GET" && method !== "HEAD") {
    init.body = req.body;
    init.duplex = "half"; // required when streaming a request body
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${BACKEND_URL}/${path}${req.nextUrl.search}`, init);
  } catch {
    return NextResponse.json({ detail: "Upstream API unreachable." }, { status: 502 });
  }

  // Stream the response straight through — works for JSON and SSE alike.
  const resHeaders = new Headers(upstream.headers);
  resHeaders.delete("content-encoding");
  resHeaders.delete("content-length");
  return new NextResponse(upstream.body, { status: upstream.status, headers: resHeaders });
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
