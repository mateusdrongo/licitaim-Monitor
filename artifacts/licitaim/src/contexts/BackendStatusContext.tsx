import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { isNetworkError, onOfflineEvent } from "@/lib/apiFetch";

type BackendStatus = "online" | "offline" | "restored";

interface BackendStatusContextValue {
  status: BackendStatus;
  /** True when the backend is unreachable (for backwards-compat consumers). */
  isOffline: boolean;
  dismiss: () => void;
}

const BackendStatusContext = createContext<BackendStatusContextValue>({
  status: "online",
  isOffline: false,
  dismiss: () => {},
});

export function useBackendStatus() {
  return useContext(BackendStatusContext);
}

const POLL_INTERVAL_MS = 5_000;
const RESTORED_DISPLAY_MS = 2_500;

/**
 * Provides both a QueryClientProvider and a BackendStatusContext.
 *
 * Network errors are detected from three sources:
 *  1. QueryCache.onError   — failed useQuery / useSuspenseQuery calls
 *  2. MutationCache.onError — failed useMutation calls
 *  3. "backend:offline" DOM event — raw apiFetch() calls outside React Query
 *     (login, register, direct fetch mutations in GerenciamentoDetalhe, etc.)
 *
 * Auto-recovery:
 *  While offline, a lightweight probe hits /api/healthz every POLL_INTERVAL_MS.
 *  On success the status transitions to "restored" for RESTORED_DISPLAY_MS,
 *  then back to "online". All queries are invalidated on recovery so stale data
 *  is refreshed automatically.
 *
 *  Two separate effects manage the two distinct phases so their cleanup
 *  functions do not interfere with each other:
 *   - Effect A (deps: [status === "offline"]) — runs the polling interval.
 *     Its cleanup only cancels the polling; it never touches the restored timer.
 *   - Effect B (deps: [status === "restored"]) — starts the auto-dismiss timer.
 *     Its cleanup cancels the timer if the component unmounts mid-display.
 */
export function BackendStatusProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<BackendStatus>("online");

  // Keep a stable ref to avoid re-creating the QueryClient on re-renders.
  const queryClientRef = useRef<QueryClient | null>(null);
  if (!queryClientRef.current) {
    queryClientRef.current = new QueryClient({
      queryCache: new QueryCache({
        onError: (error) => {
          if (isNetworkError(error)) setStatus("offline");
        },
      }),
      mutationCache: new MutationCache({
        onError: (error) => {
          if (isNetworkError(error)) setStatus("offline");
        },
      }),
      defaultOptions: {
        queries: {
          retry: 1,
          refetchOnWindowFocus: false,
        },
      },
    });
  }

  // Listen for offline events dispatched by apiFetch() (raw fetch calls outside RQ).
  useEffect(() => {
    return onOfflineEvent(() => setStatus("offline"));
  }, []);

  // Effect A: polling probe — only active while offline.
  // Cleanup only cancels the interval; it never touches the restored-display timer.
  useEffect(() => {
    if (status !== "offline") return;

    let cancelled = false;

    const probe = async () => {
      if (cancelled) return;
      try {
        const res = await fetch("/api/healthz", { method: "GET", cache: "no-store" });
        if (res.ok && !cancelled) {
          // Invalidate stale queries before the banner disappears.
          queryClientRef.current?.invalidateQueries();
          // Transition: offline → restored
          // Effect B (below) will handle restored → online after the display delay.
          setStatus("restored");
        }
      } catch {
        // Still unreachable — next tick will retry.
      }
    };

    // Run immediately so users don't wait a full interval on first recovery.
    probe();
    const intervalId = setInterval(probe, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [status === "offline"]); // eslint-disable-line react-hooks/exhaustive-deps

  // Effect B: auto-dismiss after showing the "Conexão restaurada" confirmation.
  // Lives in its own effect so Effect A's cleanup cannot cancel this timer.
  useEffect(() => {
    if (status !== "restored") return;

    const timerId = setTimeout(() => {
      setStatus("online");
    }, RESTORED_DISPLAY_MS);

    return () => clearTimeout(timerId);
  }, [status === "restored"]); // eslint-disable-line react-hooks/exhaustive-deps

  const dismiss = useCallback(() => setStatus("online"), []);

  return (
    <BackendStatusContext.Provider
      value={{
        status,
        isOffline: status === "offline",
        dismiss,
      }}
    >
      <QueryClientProvider client={queryClientRef.current}>
        {children}
      </QueryClientProvider>
    </BackendStatusContext.Provider>
  );
}
