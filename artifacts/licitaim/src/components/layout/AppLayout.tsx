import React, { useEffect, useRef } from "react";
import { useLocation } from "wouter";
import { Sidebar } from "./Sidebar";
import { useGetMe } from "@workspace/api-client-react";
import { ThemeProvider, useTheme } from "@/context/ThemeContext";

function AppLayoutInner({ children }: { children: React.ReactNode }) {
  const [location, setLocation] = useLocation();
  const { data: user, error, isLoading } = useGetMe();
  const { theme } = useTheme();

  // Keep a ref to the current location so the auth effect can read it
  // without being re-triggered on every navigation.
  const locationRef = useRef(location);
  useEffect(() => { locationRef.current = location; }, [location]);

  useEffect(() => {
    if (!isLoading && !user) {
      // Preserve the intended destination so Login can redirect back after auth.
      const intended = locationRef.current;
      const redirect = intended && intended !== "/" ? `?redirect=${encodeURIComponent(intended)}` : "";
      setLocation(`/entrar${redirect}`);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, user, setLocation]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) return null;

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
