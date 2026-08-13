import React, { useEffect, useState } from "react";
import { useLocation, useSearch } from "wouter";
import { useGetMe } from "@workspace/api-client-react";
import { Activity, ArrowRight, ShieldCheck } from "lucide-react";
import { apiFetch } from "@/lib/apiFetch";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

/** Returns the path to redirect to after a successful login. */
function useRedirectTarget(fallback = "/dashboard"): string {
  const search = useSearch();
  const params = new URLSearchParams(search);
  const raw = params.get("redirect");
  if (!raw) return fallback;
  try {
    const decoded = decodeURIComponent(raw);
    // Only allow internal paths (no protocol-relative or absolute URLs)
    if (decoded.startsWith("/") && !decoded.startsWith("//")) return decoded;
  } catch {
    // malformed – ignore
  }
  return fallback;
}

export default function Login() {
  const [, setLocation] = useLocation();
  const redirectTo = useRedirectTarget();
  const { data: user, isLoading, refetch } = useGetMe({
    query: { retry: 0 },
  });

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (user) {
      setLocation(redirectTo);
    }
  }, [user, setLocation, redirectTo]);

  const goRegister = () => setLocation("/cadastro");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      const res = await apiFetch(`${BASE}/api/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const b = body as { detail?: string | { msg: string }[]; error?: string };
        const detail = Array.isArray(b.detail)
          ? (b.detail[0]?.msg ?? "Erro ao fazer login.")
          : (b.detail ?? b.error ?? "Erro ao fazer login. Tente novamente.");
        setError(detail);
        return;
      }

      await refetch();
      setLocation(redirectTo);
    } catch {
      setError("Não foi possível conectar ao servidor. Verifique sua conexão.");
    } finally {
      setSubmitting(false);
    }
  };

  if (isLoading) return (
    <div className="min-h-screen w-full flex items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-3 text-muted-foreground">
        <svg className="w-8 h-8 animate-spin text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
        </svg>
        <span className="text-sm">Verificando sessão…</span>
      </div>
    </div>
  );

  if (user) return null;

  return (
    <div className="min-h-screen w-full flex bg-background">
      {/* Left side - Login Form */}
      <div className="w-full lg:w-1/2 flex flex-col justify-center px-8 sm:px-16 lg:px-24">
        <div className="max-w-sm w-full mx-auto space-y-8">
          <div>
            <div className="flex items-center gap-2 mb-6">
              <div className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
                <Activity className="w-6 h-6 text-primary-foreground" />
              </div>
              <h1 className="text-3xl font-bold tracking-tight text-primary">LicitAIM</h1>
            </div>
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">Acesso ao Terminal</h2>
            <p className="text-sm text-muted-foreground mt-2">
              Insira seu e-mail para acessar o ambiente seguro.
            </p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium leading-none" htmlFor="email">
                E-mail corporativo
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="nome@empresa.com.br"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                required
                disabled={submitting}
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium leading-none" htmlFor="password">
                  Senha
                </label>
                <a href="#" className="text-xs text-primary hover:underline">
                  Esqueceu a senha?
                </a>
              </div>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                required
                disabled={submitting}
              />
            </div>

            {error && (
              <p className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full flex items-center justify-center gap-2 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2 rounded-md font-medium transition-colors mt-6 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {submitting ? "Acessando…" : <><span>Acessar Plataforma</span> <ArrowRight className="w-4 h-4" /></>}
            </button>

            <p className="text-xs text-center text-muted-foreground pt-2">
              Não tem conta?{" "}
              <button type="button" onClick={goRegister} className="text-primary hover:underline font-medium">
                Criar conta grátis
              </button>
            </p>
          </form>

          <div className="flex items-center gap-2 text-xs text-muted-foreground justify-center pt-8">
            <ShieldCheck className="w-4 h-4" />
            Ambiente seguro e criptografado
          </div>
        </div>
      </div>

      {/* Right side - Visual/Brand */}
      <div className="hidden lg:flex w-1/2 bg-primary p-12 flex-col justify-between relative overflow-hidden">
        <div className="absolute inset-0 opacity-10 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-white via-transparent to-transparent" />
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMSIgY3k9IjEiIHI9IjEiIGZpbGw9InJnYmEoMjU1LDI1NSwyNTUsMC4xKSIvPjwvc3ZnPg==')] [mask-image:linear-gradient(to_bottom,white,transparent)]" />
        
        <div className="relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 text-primary-foreground text-sm font-medium border border-white/20 backdrop-blur-sm">
            <Activity className="w-4 h-4" /> Sistema Operacional
          </div>
        </div>
        
        <div className="relative z-10 max-w-lg">
          <h2 className="text-4xl font-bold text-primary-foreground leading-tight mb-4">
            A inteligência por trás das grandes licitações.
          </h2>
          <p className="text-primary-foreground/80 text-lg">
            Monitoramento de editais em tempo real, predição de preços e análise da concorrência num cockpit desenhado para velocidade.
          </p>
        </div>
      </div>
    </div>
  );
}
