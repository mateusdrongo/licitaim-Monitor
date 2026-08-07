import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { isNetworkError, onOfflineEvent } from "@/lib/apiFetch";

interface BackendStatusContextValue {
  isOffline: boolean;
  dismiss: () => void;
}

const BackendStatusContext = createContext<BackendStatusContextValue>({
  isOffline: false,
  dismiss: () => {},
});

export function useBackendStatus() {
  return useContext(BackendStatusContext);
}

/**
 * Provides both a QueryClientProvider and a BackendStatusContext.
 *
 * Network errors are detected from three sources:
 *  1. QueryCache.onError   — failed useQuery / useSuspenseQuery calls
 *  2. MutationCache.onError — failed useMutation calls
 *  3. "backend:offline" DOM event — raw apiFetch() calls outside React Query
 *     (login, register, direct fetch mutations in GerenciamentoDetalhe, etc.)
 */
export function BackendStatusProvider({ children }: { children: React.ReactNode }) {
  const [isOffline, setIsOffline] = useState(false);
  const markOffline = useCallback(() => setIsOffline(true), []);

  // Keep a stable ref to avoid re-creating the QueryClient on re-renders.
  const queryClientRef = useRef<QueryClient | null>(null);
  if (!queryClientRef.current) {
    queryClientRef.current = new QueryClient({
      queryCache: new QueryCache({
        onError: (error) => {
          if (isNetworkError(error)) markOffline();
        },
      }),
      mutationCache: new MutationCache({
        onError: (error) => {
          if (isNetworkError(error)) markOffline();
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
    return onOfflineEvent(markOffline);
  }, [markOffline]);

  const dismiss = useCallback(() => setIsOffline(false), []);

  return (
    <BackendStatusContext.Provider value={{ isOffline, dismiss }}>
      <QueryClientProvider client={queryClientRef.current}>
        {children}
      </QueryClientProvider>
    </BackendStatusContext.Provider>
  );
}
