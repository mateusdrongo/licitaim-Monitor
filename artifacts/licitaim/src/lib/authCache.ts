/**
 * Thin sessionStorage wrapper for the authenticated User object.
 *
 * sessionStorage is used (not localStorage) so the cache is automatically
 * cleared when the browser tab is closed, matching the session-cookie lifetime.
 *
 * The cache is written after every successful /api/auth/me response and read
 * on the next page load to seed React Query's initialData, eliminating the
 * full-screen spinner for returning users.
 */

import type { User } from "@workspace/api-client-react";

const KEY = "licitaim_auth_user";

export function getAuthCache(): User | undefined {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return undefined;
    return JSON.parse(raw) as User;
  } catch {
    return undefined;
  }
}

export function setAuthCache(user: User): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(user));
  } catch {
    // Ignore — storage may be unavailable in certain contexts.
  }
}

export function clearAuthCache(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    // Ignore.
  }
}
