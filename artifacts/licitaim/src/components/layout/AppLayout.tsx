import React, { useEffect, useRef } from "react";
import { useLocation } from "wouter";
import { Sidebar } from "./Sidebar";
import { useGetMe, getGetMeQueryKey } from "@workspace/api-client-react";
import { ThemeProvider, useTheme } from "@/context/ThemeContext";
import { getAuthCache, setAuthCache, clearAuthCache } from "@/lib/authCache";

function AppLayoutInner({ children }: { children: React.ReactNode }) {
  const [location, setLocation] = useLocation();

  // Seed the query with whatever is in sessionStorage so React Query has data
  // immediately on page load. Setting initialDataUpdatedAt to 0 marks the data
  // as stale so it is still revalidated in the background, but the spinner is
  // skipped entirely when a cached user exists.
  const cachedUser = getAuthCache();
  const { data: user, error, isLoading } = useGetMe({
    query: {
      queryKey: getGetMeQueryKey(),
      initialData: cachedUser,
      initialDataUpdatedAt: cachedUser ? 0 : undefined,
    },
  });
  const { theme } = useTheme();

  // IMPORTANT: React Query retains `initialData` even when a background
  // revalidation fails, so `user` stays truthy while `error` is set.
  // We must treat `error` as authoritative — the session was rejected by the
  // server regardless of what the local cache says.
  const authRejected = !!error;

  // Persist successful auth responses so the next hard-refresh can use them.
  // Never write when the server has rejected the session.
  useEffect(() => {
    if (user && !authRejected) setAuthCache(user);
  }, [user, authRejected]);

  // Keep a ref to the current location so the auth effect can read it
  // without being re-triggered on every navigation.
  const locationRef = useRef(location);
  useEffect(() => { locationRef.current = location; }, [location]);

  useEffect(() => {
    // Redirect when there is definitively no authenticated user — either the
    // server explicitly rejected the session (authRejected) or the query
    // finished with no data at all.
    const shouldRedirect = authRejected || (!isLoading && !user);
    if (!shouldRedirect) return;

    if (authRejected) clearAuthCache();

    // Preserve the intended destination so Login can redirect back after auth.
    const intended = locationRef.current;
    const redirect = intended && intended !== "/" ? `?redirect=${encodeURIComponent(intended)}` : "";
    setLocation(`/entrar${redirect}`);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, user, authRejected, setLocation]);

  // Only show the full-screen spinner when there is no cached user to display.
  // When initialData was provided, isLoading is false and revalidation runs
  // in the background — no spinner needed.
  if (isLoading && !cachedUser) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // Do not render the authenticated layout if the server rejected the session,
  // even when initialData from the cache is still present in `user`.
  if (!user || authRejected) return null;

  return (
    /* A classe `dark` é aplicada AQUI, isolada do resto da aplicação */
    <div className={`${theme === "dark" ? "dark" : ""} min-h-screen bg-background text-foreground flex`}>
      <Sidebar />
      <main className="flex-1 ml-64 min-h-screen overflow-x-hidden">
        {children}
      </main>
    </div>
  );
}

export function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <AppLayoutInner>{children}</AppLayoutInner>
    </ThemeProvider>
  );
}
