/**
 * Thin wrapper around fetch that dispatches a "backend:offline" CustomEvent
 * whenever a network-level failure occurs (TypeError / connection refused).
 * The BackendStatusProvider listens for this event to show the offline banner.
 *
 * Use this instead of raw fetch() for all API calls so the global banner fires
 * consistently — including outside React Query (login, register, mutations, etc.).
 */

const OFFLINE_EVENT = "backend:offline";

/** Call from outside React to signal a network failure. */
export function dispatchOfflineEvent(): void {
  window.dispatchEvent(new CustomEvent(OFFLINE_EVENT));
}

/** Subscribe to the offline event; returns an unsubscribe function. */
export function onOfflineEvent(handler: () => void): () => void {
  window.addEventListener(OFFLINE_EVENT, handler);
  return () => window.removeEventListener(OFFLINE_EVENT, handler);
}

/** Returns true when the error looks like a network / backend-offline failure. */
export function isNetworkError(error: unknown): boolean {
  if (error instanceof TypeError) {
    return true; // "Failed to fetch", "NetworkError when attempting to fetch resource"
  }
  if (error instanceof Error) {
    const msg = error.message.toLowerCase();
    return (
      msg.includes("failed to fetch") ||
      msg.includes("network error") ||
      msg.includes("networkerror") ||
      msg.includes("load failed") // Safari
    );
  }
  return false;
}

/**
 * Drop-in replacement for fetch() that automatically fires the offline banner
 * on network errors. Signature is identical to the global fetch.
 */
export async function apiFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch (err) {
    if (isNetworkError(err)) {
      dispatchOfflineEvent();
    }
    throw err;
  }
}
