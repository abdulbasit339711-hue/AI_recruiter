"use client";

import { useSyncExternalStore } from "react";

function getCookie(name: string): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : "";
}

// Minimal external store that tracks the user_role cookie value.
function subscribe(cb: () => void) {
  // Re-read on focus (tab switch back) to catch token expiry / role changes.
  window.addEventListener("focus", cb);
  return () => window.removeEventListener("focus", cb);
}

export type UserRole = "admin" | "hr";

export function useRole(): UserRole {
  const raw = useSyncExternalStore(subscribe, () => getCookie("user_role"), () => "admin");
  return raw === "hr" ? "hr" : "admin";
}

export function useIsAdmin(): boolean {
  return useRole() === "admin";
}
