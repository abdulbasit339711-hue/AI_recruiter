// Signed admin session token (server-only). The login cookie used to BE the raw
// ADMIN_API_TOKEN — a cookie leak was then a full backend compromise. Instead we mint
// a short-lived HMAC-signed opaque token: it grants a UI session but is NOT the backend
// secret, and rotating ADMIN_API_TOKEN (the signing key) invalidates all sessions.
//
// Uses node:crypto, so this module must only be imported from Node-runtime code
// (route handlers: api/login, api/admin proxy). Edge middleware does a crypto-free
// expiry check instead (see middleware.ts) — the proxy is the authoritative gate.
import { createHmac, timingSafeEqual, randomBytes } from "crypto";

const TTL_MS = 8 * 60 * 60 * 1000; // 8 hours

// Prefer a dedicated SESSION_SECRET; fall back to ADMIN_API_TOKEN so no new config is
// required (the cookie is still a signed token, never the raw secret).
function signingKey(): string {
  return process.env.SESSION_SECRET || process.env.ADMIN_API_TOKEN || "";
}

function sign(body: string): Buffer {
  return createHmac("sha256", signingKey()).update(body).digest();
}

/** Mint a signed session token: base64url(payload).base64url(hmac). */
export function mintSession(): string {
  const body = Buffer.from(
    JSON.stringify({ sid: randomBytes(9).toString("base64url"), exp: Date.now() + TTL_MS })
  ).toString("base64url");
  return `${body}.${sign(body).toString("base64url")}`;
}

/** Verify signature AND expiry. Authoritative check (used by the proxy + login). */
export function verifySession(token?: string | null): boolean {
  if (!token || !signingKey()) return false;
  const [body, sig] = token.split(".");
  if (!body || !sig) return false;
  const expected = sign(body);
  let got: Buffer;
  try {
    got = Buffer.from(sig, "base64url");
  } catch {
    return false;
  }
  if (expected.length !== got.length || !timingSafeEqual(expected, got)) return false;
  try {
    const { exp } = JSON.parse(Buffer.from(body, "base64url").toString());
    return typeof exp === "number" && Date.now() < exp;
  } catch {
    return false;
  }
}

/** Constant-time string equality (lengths hashed first so they never leak). */
export function safeEqual(a: string, b: string): boolean {
  const ha = createHmac("sha256", "cmp").update(a).digest();
  const hb = createHmac("sha256", "cmp").update(b).digest();
  return timingSafeEqual(ha, hb);
}

export const SESSION_COOKIE = "admin_session";
export const SESSION_MAX_AGE_S = TTL_MS / 1000;
