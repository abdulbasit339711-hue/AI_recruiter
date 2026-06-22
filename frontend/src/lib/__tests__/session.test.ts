import { describe, it, expect, beforeAll } from "vitest";
import { mintSession, verifySession, safeEqual } from "@/lib/session";

beforeAll(() => {
  // session.ts reads the signing key at call time, so setting it here is in time.
  process.env.SESSION_SECRET = "test-session-secret-value";
});

describe("session token", () => {
  it("mints a token that verifies and is NOT the raw secret", () => {
    const t = mintSession();
    expect(verifySession(t)).toBe(true);
    expect(t.includes(process.env.SESSION_SECRET as string)).toBe(false);
  });

  it("rejects a tampered signature", () => {
    const t = mintSession();
    const tampered = t.slice(0, -3) + (t.endsWith("x") ? "yyy" : "xxx");
    expect(verifySession(tampered)).toBe(false);
  });

  it("rejects junk / empty / missing", () => {
    expect(verifySession("not-a-token")).toBe(false);
    expect(verifySession("")).toBe(false);
    expect(verifySession(undefined)).toBe(false);
    expect(verifySession("a.b.c")).toBe(false);
  });

  it("safeEqual is correct", () => {
    expect(safeEqual("abc", "abc")).toBe(true);
    expect(safeEqual("abc", "abd")).toBe(false);
    expect(safeEqual("abc", "abcd")).toBe(false);
  });
});
