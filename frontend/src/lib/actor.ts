"use client";

/** Who is performing an HR action, for the candidate audit trail.
 *
 * The backend uses a single shared admin token (no per-user accounts), so there
 * is no server-side identity to attribute changes to. As a pragmatic stand-in,
 * the operator can record an identifier at sign-in; it's kept in localStorage and
 * stamped onto status/score/note changes — far more useful than a hardcoded
 * "hr@company.com". Replace with a real identity claim if accounts are added.
 */

const KEY = "hr_actor";
const FALLBACK = "unknown@hr";

export function setHrActor(identifier: string): void {
  if (typeof window === "undefined") return;
  const v = identifier.trim();
  if (v) window.localStorage.setItem(KEY, v);
}

export function getHrActor(): string {
  if (typeof window === "undefined") return FALLBACK;
  return window.localStorage.getItem(KEY)?.trim() || FALLBACK;
}
