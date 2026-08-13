import React, { useState } from "react";
import { useLocation } from "wouter";
import { Activity, ArrowLeft, ArrowRight, ShieldCheck } from "lucide-react";
import { apiFetch } from "@/lib/apiFetch";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

export default function EsqueceuSenha() {
  const [, setLocation] = useLocation();

  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      const res = await apiFetch(`${BASE}/api/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const b = body as { detail?: string };
        setError(b.detail ?? "Erro ao processar solicitação. Tente novamente.");
        return;
      }

      setSubmitted(true);
    } catch {
      setError("Não foi possível conectar ao servidor. Verifique sua conexão.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex bg-background">
      {/* Left side - Form */}
      <div className="w-full lg:w-1/2 flex flex-col justify-center px-8 sm:px-16 lg:px-24">
        <div className="max-w-sm w-full mx-auto space-y-8">
          <div>
            <div className="flex items-center gap-2 mb-6">
              <div className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
                <Activity className="w-6 h-6 text-primary-foreground" />
              </div>
              <h1 className="text-3xl font-bold tracking-tight text-primary">LicitAIM</h1>
            </div>
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">
              Redefinir senha
            </h2>
            <p className="text-sm text-muted-foreground mt-2">
              Informe o e-mail da sua conta e enviaremos um link para redefinição.
            </p>
          </div>

          {submitted ? (
            <div className="space-y-4">
              <div className="rounded-md bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-800">
                Solicitação recebida. Se o e-mail estiver cadastrado, você receberá o link em breve.
              </div>

              <button
                type="button"
                onClick={() => setLocation("/entrar")}
                className="flex items-center gap-1 text-sm text-primary hover:underline"
              >
                <ArrowLeft className="w-4 h-4" /> Voltar ao login
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
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

              {error && (
                <p className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={submitting}
                className="w-full flex items-center justify-center gap-2 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2 rounded-md font-medium transition-colors mt-2 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {submitting ? "Enviando…" : <><span>Enviar link de redefinição</span> <ArrowRight className="w-4 h-4" /></>}
              </button>

              <button
                type="button"
                onClick={() => setLocation("/entrar")}
                className="flex items-center gap-1 text-sm text-primary hover:underline"
              >
                <ArrowLeft className="w-4 h-4" /> Voltar ao login
              </button>
            </form>
          )}

          <div className="flex items-center gap-2 text-xs text-muted-foreground justify-center pt-8">
            <ShieldCheck className="w-4 h-4" />
            Ambiente seguro e criptografado
          </div>
        </div>
      </div>

      {/* Right side - Brand */}
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
