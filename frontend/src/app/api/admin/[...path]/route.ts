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
//   - Admin-only mutations (job CRUD, reprocess, score-override) are gated to the
//     "admin" role. HR sessions can read/update candidate status but cannot manage jobs.

import { NextRequest, NextResponse } from "next/server";
import { verifySession, getSessionRole, SESSION_COOKIE } from "@/lib/session";

export const dynamic = "force-dynamic";

const BACKEND_URL = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const ADMIN_API_TOKEN = process.env.ADMIN_API_TOKEN || "";

function isPublic(method: string, path: string): boolean {
  if (method === "GET" && path === "jobs") return true; // careers listing
  if (method === "GET" && /^jobs\/\d+$/.test(path)) return true; // view one job
  if (method === "GET" && path === "iq-test") return true; // fetch pre-application IQ test
  if (method === "POST" && path === "iq-test/submit") return true; // submit IQ answers
  if (method === "POST" && path === "upload") return true; // submit a resume
  // Org whitelabel: public branding + job listing per org slug
  if (method === "GET" && /^orgs\/[^/]+$/.test(path)) return true;
  if (method === "GET" && /^orgs\/[^/]+\/jobs$/.test(path)) return true;
  // Candidate availability form (token-gated, no admin session needed)
  if (/^availability\/[^/]+$/.test(path)) return true;
  // Candidate interview waiting room (token-gated)
  if (method === "GET" && /^interview-room\/[^/]+$/.test(path)) return true;
  return false;
}

// Actions that require the admin role — HR users are denied with 403.
function isAdminOnly(method: string, path: string): boolean {
  if (method === "POST" && path === "jobs") return true; // create job
  if (
    (method === "PUT" || method === "PATCH" || method === "DELETE") &&
    /^jobs\/\d+$/.test(path)
  )
    return true; // edit / archive / delete job
  if (method === "POST" && /^jobs\/\d+\/(reprocess|email)$/.test(path)) return true;
  if (
    (method === "PUT" || method === "POST") &&
    /^jobs\/\d+\/scoring-weights$/.test(path)
  )
    return true;
  if (method === "POST" && /^candidates\/\d+\/reprocess$/.test(path)) return true;
  if (method === "PATCH" && /^candidates\/\d+\/score-override$/.test(path)) return true;
  if (method === "POST" && /^candidates\/\d+\/annotate-video$/.test(path)) return true;
  // Org management: only admin can create or delete orgs
  if (method === "POST" && path === "orgs") return true;
  if (method === "DELETE" && /^orgs\/\d+$/.test(path)) return true;
  // Settings: admin only
  if (method === "PATCH" && /^settings\/.+$/.test(path)) return true;
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
    // Authoritative gate: the cookie must be a valid SIGNED session token.
    const sessionToken = req.cookies.get(SESSION_COOKIE)?.value;
    if (!ADMIN_API_TOKEN || !verifySession(sessionToken)) {
      return NextResponse.json({ detail: "Not authenticated." }, { status: 401 });
    }

    // Role-based access: reject HR users from admin-only mutations.
    if (isAdminOnly(method, path) && getSessionRole(sessionToken) === "hr") {
      return NextResponse.json(
        { detail: "Admin role required for this action." },
        { status: 403 }
      );
    }
  }

  const headers = new Headers();
  const ct = req.headers.get("content-type");
  if (ct) headers.set("content-type", ct);
  const accept = req.headers.get("accept");
  if (accept) headers.set("accept", accept);
  // Forward Range so the browser can seek/scrub audio & video (the backend serves
  // 206 Partial Content via FileResponse; without this the player can't skip).
  const range = req.headers.get("range");
  if (range) headers.set("range", range);
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
