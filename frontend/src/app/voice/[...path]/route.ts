// Same-origin streaming proxy to the voice service (Pipecat, :7860).
//
// Why a route handler and not a next.config rewrite: the interview page opens an
// SSE stream (/voice/events) for the live transcript. Next's rewrite proxy buffers
// long-lived responses and tears them down with a BodyTimeoutError. A route handler
// lets us pass the upstream ReadableStream straight through, so SSE streams cleanly.
//
// Keeping the voice service same-origin means the phone only talks to ONE origin
// (one ngrok tunnel) — no CORS, no ngrok interstitial on cross-origin fetches.

import { NextRequest } from "next/server";

export const dynamic = "force-dynamic"; // never cache; always proxy live
export const runtime = "nodejs";

const VOICE_TARGET = (process.env.VOICE_PROXY_TARGET || "http://127.0.0.1:7860").replace(/\/$/, "");

// Hop-by-hop headers must not be forwarded.
const STRIP = new Set([
  "host",
  "connection",
  "content-length",
  "transfer-encoding",
  "keep-alive",
  "upgrade",
]);

async function proxy(req: NextRequest, path: string[]): Promise<Response> {
  const search = req.nextUrl.search;
  const url = `${VOICE_TARGET}/${path.join("/")}${search}`;

  const headers = new Headers();
  req.headers.forEach((v, k) => {
    if (!STRIP.has(k.toLowerCase())) headers.set(k, v);
  });

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: "manual",
  };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = req.body;
    // @ts-expect-error — undici option: required when streaming a request body.
    // Only set with a body; on a bodyless GET it makes undici hang waiting for one
    // (which stalled the SSE /events stream).
    init.duplex = "half";
  }

  let upstream: Response;
  try {
    upstream = await fetch(url, init);
  } catch (e) {
    return new Response(`voice proxy error: ${(e as Error).message}`, { status: 502 });
  }

  const respHeaders = new Headers();
  upstream.headers.forEach((v, k) => {
    if (!STRIP.has(k.toLowerCase())) respHeaders.set(k, v);
  });

  const contentType = upstream.headers.get("content-type") || "";
  const isStream = contentType.includes("text/event-stream");

  if (isStream && upstream.body) {
    // SSE: manually pump the upstream reader into a fresh ReadableStream and add
    // anti-buffering headers. Simply returning upstream.body lets Next buffer the
    // whole (never-ending) response, so headers never flush and the live transcript
    // never streams. Pumping chunk-by-chunk forces incremental delivery.
    respHeaders.set("content-type", "text/event-stream; charset=utf-8");
    respHeaders.set("cache-control", "no-cache, no-transform");
    respHeaders.set("connection", "keep-alive");
    respHeaders.set("x-accel-buffering", "no");

    const reader = upstream.body.getReader();
    const stream = new ReadableStream<Uint8Array>({
      async pull(controller) {
        try {
          const { done, value } = await reader.read();
          if (done) {
            controller.close();
            return;
          }
          controller.enqueue(value);
        } catch {
          controller.close();
        }
      },
      cancel() {
        reader.cancel().catch(() => {});
      },
    });

    return new Response(stream, { status: upstream.status, headers: respHeaders });
  }

  // Non-streaming responses (validate, chat, questions): pass through as-is.
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: respHeaders,
  });
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function OPTIONS(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
