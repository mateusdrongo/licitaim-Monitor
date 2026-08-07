import React, { useEffect, useState } from "react";
import { useLocation } from "wouter";
import { useGetMe } from "@workspace/api-client-react";
import { Activity, ArrowRight, ShieldCheck } from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

export default function Cadastro() {
  const [, setLocation] = useLocation();
  const { data: user, isLoading, refetch } = useGetMe();

  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [empresa, setEmpresa] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (user) setLocation("/dashboard");
  }, [user, setLocation]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const res = await fetch(`${BASE}/api/auth/register`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nome, email, password, empresa: empresa || undefined }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError((body as { detail?: string }).detail ?? "Erro ao criar conta.");
        return;
      }
      await refetch();
      setLocation("/dashboard");
    } catch {
      setError("Não foi possível conectar ao servidor.");
    } finally {
      setSubmitting(false);
    }
  };

  if (isLoading) return null;

  return (
    <div className="min-h-screen w-full flex bg-background">
      <div className="w-full lg:w-1/2 flex flex-col justify-center px-8 sm:px-16 lg:px-24">
        <div className="max-w-sm w-full mx-auto space-y-7">
          <div>
            <div className="flex items-center gap-2 mb-6">
              <div className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
                <Activity className="w-6 h-6 text-primary-foreground" />
              </div>
              <h1 className="text-3xl font-bold tracking-tight text-primary">LicitAIM</h1>
            </div>
            <h2 className="text-2xl font-semibold tracking-tight">Criar conta</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Comece gratuitamente. Sem cartão de crédito.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {[
              { id: "nome", label: "Nome completo", type: "text", value: nome, set: setNome, placeholder: "João Silva", required: true },
              { id: "email", label: "E-mail corporativo", type: "email", value: email, set: setEmail, placeholder: "nome@empresa.com.br", required: true },
              { id: "empresa", label: "Empresa (opcional)", type: "text", value: empresa, set: setEmpresa, placeholder: "Minha Empresa Ltda", required: false },
              { id: "password", label: "Senha", type: "password", value: password, set: setPassword, placeholder: "Mínimo 8 caracteres", required: true },
            ].map(({ id, label, type, value, set, placeholder, required }) => (
              <div key={id} className="space-y-1.5">
                <label className="text-sm font-medium leading-none" htmlFor={id}>{label}</label>
                <input
                  id={id} type={type} value={value} placeholder={placeholder} required={required}
                  onChange={(e) => set(e.target.value)} disabled={submitting}
                  className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                />
              </div>
            ))}

            {error && (
              <p className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit" disabled={submitting}
              className="w-full flex items-center justify-center gap-2 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 rounded-md font-medium transition-colors mt-2 disabled:opacity-60"
            >
              {submitting ? "Criando conta…" : <><span>Criar conta grátis</span><ArrowRight className="w-4 h-4" /></>}
            </button>

            <p className="text-xs text-center text-muted-foreground">
              Já tem conta?{" "}
              <button type="button" onClick={() => setLocation("/entrar")} className="text-primary hover:underline font-medium">
                Entrar
              </button>
            </p>
          </form>

          <div className="flex items-center gap-2 text-xs text-muted-foreground justify-center">
            <ShieldCheck className="w-4 h-4" />
            Ambiente seguro · LGPD compliant
          </div>
        </div>
      </div>

      <div className="hidden lg:flex w-1/2 bg-primary p-12 flex-col justify-between relative overflow-hidden">
        <div className="absolute inset-0 opacity-10 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-white via-transparent to-transparent" />
        <div className="relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 text-primary-foreground text-sm font-medium border border-white/20">
            <Activity className="w-4 h-4" /> 14 dias grátis do plano Pro
          </div>
        </div>
        <div className="relative z-10 max-w-lg">
          <h2 className="text-4xl font-bold text-primary-foreground leading-tight mb-4">
            Comece a vencer mais licitações hoje.
          </h2>
          <p className="text-primary-foreground/80 text-lg">
            Mais de 3.200 empresas já usam o LicitAIM para monitorar, participar e vencer licitações públicas no Brasil.
          </p>
        </div>
      </div>
    </div>
  );
}
