// Short-link redirect for interview invites.
//
// The signed interview token is ~330 chars, so the full /interview/<token> URL
// wraps across several terminal lines; copying it pulls in line-break whitespace
// and wrap markers that corrupt the token's signature. This route maps a SHORT
// code to the full token and 302-redirects to /interview/<token>, so the browser
// receives the long token via the Location header — the human only ever copies
// the short, unwrappable URL.
//
// Mapping lives in a JSON file ({ "<code>": "<token>" }) so it can be regenerated
// without code changes; path overridable via SHORTLINK_FILE.

import { NextRequest, NextResponse } from "next/server";
import { readFile } from "fs/promises";
import path from "path";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const MAP_FILE = process.env.SHORTLINK_FILE || path.join(process.cwd(), "interview-links.json");

export async function GET(req: NextRequest, ctx: { params: Promise<{ code: string }> }) {
  const { code } = await ctx.params;
  try {
    const map = JSON.parse(await readFile(MAP_FILE, "utf8")) as Record<string, string>;
    const token = map[code];
    if (token) {
      // RELATIVE Location: the browser resolves it against the origin it actually
      // came from (e.g. the ngrok domain), so this works behind a proxy without
      // Next trusting/forwarding the host. An absolute URL from req.url would point
      // at localhost behind ngrok and fail on the candidate's phone.
      return new NextResponse(null, { status: 302, headers: { Location: `/interview/${token}` } });
    }
  } catch {
    /* fall through to 404 */
  }
  return new NextResponse("Unknown or expired interview link.", { status: 404 });
}
