import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ShieldCheck,
  Plus,
  Pencil,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  Clock,
  X,
} from "lucide-react";
import { apiFetch } from "@/lib/apiFetch";
import { PageErrorState } from "@/components/PageErrorState";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

interface Certidao {
  id: number;
  nome: string;
  tipo: string;
  orgaoEmissor: string | null;
  numero: string | null;
  dataEmissao: string | null;
  dataVencimento: string | null;
  status: "ativa" | "vencida" | "a_vencer" | "sem_vencimento";
  descricao: string | null;
  criadoEm: string;
}

function useCertidoes() {
  return useQuery<Certidao[]>({
    queryKey: ["certidoes"],
    queryFn: async () => {
      const res = await apiFetch(`${BASE}/api/certidoes`, { credentials: "include" });
      if (!res.ok) throw new Error("Erro");
      return res.json();
    },
    retry: 2,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10_000),
  });
}

const TIPOS = [
  { value: "fgts", label: "FGTS" },
  { value: "receita_federal", label: "Receita Federal (CND)" },
  { value: "inss", label: "INSS" },
  { value: "trabalhista", label: "Trabalhista (CNDT)" },
  { value: "estadual", label: "Certidão Estadual" },
  { value: "municipal", label: "Certidão Municipal" },
  { value: "balanco", label: "Balanço Patrimonial" },
  { value: "contrato_social", label: "Contrato Social" },
  { value: "procuracao", label: "Procuração" },
  { value: "outro", label: "Outro" },
];

const statusConfig: Record<string, { label: string; icon: React.ReactNode; cls: string }> = {
  ativa:          { label: "Ativa",           icon: <CheckCircle2 className="w-3.5 h-3.5" />, cls: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" },
  vencida:        { label: "Vencida",         icon: <AlertTriangle className="w-3.5 h-3.5" />, cls: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" },
  a_vencer:       { label: "A vencer",        icon: <Clock className="w-3.5 h-3.5" />, cls: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" },
  aVencer:        { label: "A vencer",        icon: <Clock className="w-3.5 h-3.5" />, cls: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" },
  sem_vencimento: { label: "Sem vencimento",  icon: <CheckCircle2 className="w-3.5 h-3.5" />, cls: "bg-muted text-muted-foreground" },
  semVencimento:  { label: "Sem vencimento",  icon: <CheckCircle2 className="w-3.5 h-3.5" />, cls: "bg-muted text-muted-foreground" },
  sem_prazo:      { label: "Sem prazo",       icon: <CheckCircle2 className="w-3.5 h-3.5" />, cls: "bg-muted text-muted-foreground" },
  semPrazo:       { label: "Sem prazo",       icon: <CheckCircle2 className="w-3.5 h-3.5" />, cls: "bg-muted text-muted-foreground" },
};

const STATUS_FALLBACK = { label: "—", icon: <CheckCircle2 className="w-3.5 h-3.5" />, cls: "bg-muted text-muted-foreground" };

interface FormData {
  nome: string;
  tipo: string;
  orgaoEmissor: string;
  numero: string;
  dataEmissao: string;
  dataVencimento: string;
  descricao: string;
}

const EMPTY_FORM: FormData = { nome: "", tipo: "receita_federal", orgaoEmissor: "", numero: "", dataEmissao: "", dataVencimento: "", descricao: "" };

export default function Certidoes() {
  const qc = useQueryClient();
  const { data, isLoading, isError, error, refetch } = useCertidoes();
  const [modal, setModal] = useState<"create" | number | null>(null); // number = editing id
  const [form, setForm] = useState<FormData>(EMPTY_FORM);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["certidoes"] });

  const criar = useMutation({
    mutationFn: async (body: FormData) => {
      const res = await apiFetch(`${BASE}/api/certidoes`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Erro ao criar");
      return res.json();
    },
    onSuccess: () => { invalidate(); setModal(null); setForm(EMPTY_FORM); },
  });

  const atualizar = useMutation({
    mutationFn: async ({ id, body }: { id: number; body: Partial<FormData> }) => {
      const res = await apiFetch(`${BASE}/api/certidoes/${id}`, {
        method: "PATCH", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Erro ao atualizar");
      return res.json();
    },
    onSuccess: () => { invalidate(); setModal(null); setForm(EMPTY_FORM); },
  });

  const remover = useMutation({
    mutationFn: async (id: number) => {
      await apiFetch(`${BASE}/api/certidoes/${id}`, { method: "DELETE", credentials: "include" });
    },
    onSuccess: invalidate,
  });

  const openEdit = (cert: Certidao) => {
    setForm({
      nome: cert.nome,
      tipo: cert.tipo,
      orgaoEmissor: cert.orgaoEmissor ?? "",
      numero: cert.numero ?? "",
      dataEmissao: cert.dataEmissao ?? "",
      dataVencimento: cert.dataVencimento ?? "",
      descricao: cert.descricao ?? "",
    });
    setModal(cert.id);
  };

  const handleSubmit = () => {
    const payload = {
      nome: form.nome,
      tipo: form.tipo,
      orgaoEmissor: form.orgaoEmissor || undefined,
      numero: form.numero || undefined,
      dataEmissao: form.dataEmissao || undefined,
      dataVencimento: form.dataVencimento || undefined,
      descricao: form.descricao || undefined,
    };
    if (typeof modal === "number") {
      atualizar.mutate({ id: modal, body: payload });
    } else {
      criar.mutate(form);
    }
  };

  const diffLabel = (dt: string | null) => {
    if (!dt) return null;
    const diff = Math.ceil((new Date(dt).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
    if (diff < 0) return `venceu há ${Math.abs(diff)} dias`;
    if (diff === 0) return "vence hoje";
    return `vence em ${diff} dias`;
  };

  const certidoesOrd = [...(data ?? [])].sort((a, b) => {
    const order = { vencida: 0, a_vencer: 1, ativa: 2, sem_vencimento: 3 };
    return (order[a.status] ?? 3) - (order[b.status] ?? 3);
  });

  const summary = {
    total: data?.length ?? 0,
    ativas: data?.filter((c) => c.status === "ativa").length ?? 0,
    aVencer: data?.filter((c) => c.status === "a_vencer").length ?? 0,
    vencidas: data?.filter((c) => c.status === "vencida").length ?? 0,
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <ShieldCheck className="w-8 h-8 text-primary" /> Certidões & Compliance
          </h1>
          <p className="text-muted-foreground mt-1">Gestão de certidões com alertas automáticos de vencimento.</p>
        </div>
        <button
          onClick={() => { setForm(EMPTY_FORM); setModal("create"); }}
          className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <Plus className="w-4 h-4" /> Nova Certidão
        </button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Total", value: summary.total, cls: "text-foreground" },
          { label: "Ativas", value: summary.ativas, cls: "text-emerald-600" },
          { label: "A vencer (30d)", value: summary.aVencer, cls: "text-amber-600" },
          { label: "Vencidas", value: summary.vencidas, cls: "text-red-600" },
        ].map((s) => (
          <div key={s.label} className="bg-card border border-border rounded-xl p-4 text-center">
            <div className={`text-2xl font-bold font-mono ${s.cls}`}>{s.value}</div>
            <div className="text-xs text-muted-foreground mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* List */}
      {isError ? (
        <PageErrorState error={error} onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-20 bg-muted animate-pulse rounded-xl" />)}</div>
      ) : certidoesOrd.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center border-2 border-dashed border-border rounded-xl">
          <ShieldCheck className="w-12 h-12 text-muted-foreground mb-4 opacity-40" />
          <h3 className="font-semibold">Nenhuma certidão cadastrada</h3>
          <p className="text-sm text-muted-foreground mt-1">Cadastre as certidões da sua empresa para receber alertas de vencimento.</p>
          <button onClick={() => { setForm(EMPTY_FORM); setModal("create"); }} className="mt-4 flex items-center gap-2 text-primary text-sm font-medium hover:underline">
            <Plus className="w-4 h-4" /> Cadastrar primeira certidão
          </button>
        </div>
      ) : (
        <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
          <div className="divide-y divide-border">
            {certidoesOrd.map((cert) => {
              const st = statusConfig[cert.status] ?? STATUS_FALLBACK;
              const tipo = TIPOS.find(t => t.value === cert.tipo)?.label ?? cert.tipo;
              return (
                <div key={cert.id} className="p-5 flex items-start gap-4 hover:bg-muted/30 transition-colors group">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold text-sm">{cert.nome}</h3>
                      <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${st.cls}`}>
                        {st.icon} {st.label}
                      </span>
                      <span className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded">{tipo}</span>
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-muted-foreground">
                      {cert.orgaoEmissor && <span>Órgão: <span className="font-medium text-foreground">{cert.orgaoEmissor}</span></span>}
                      {cert.numero && <span>Nº <span className="font-mono text-foreground">{cert.numero}</span></span>}
                      {cert.dataEmissao && <span>Emissão: {new Date(cert.dataEmissao + "T12:00:00").toLocaleDateString("pt-BR")}</span>}
                      {cert.dataVencimento && (
                        <span className={cert.status === "vencida" ? "text-red-600 font-medium" : cert.status === "a_vencer" ? "text-amber-600 font-medium" : ""}>
                          Vencimento: {new Date(cert.dataVencimento + "T12:00:00").toLocaleDateString("pt-BR")}
                          {" "}({diffLabel(cert.dataVencimento)})
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                    <button onClick={() => openEdit(cert)} className="p-1.5 rounded-md hover:bg-primary/10 text-primary transition-colors">
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => { if (confirm("Remover esta certidão?")) remover.mutate(cert.id); }}
                      className="p-1.5 rounded-md hover:bg-destructive/10 text-destructive transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Modal */}
      {modal !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-lg mx-4 p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold">{typeof modal === "number" ? "Editar Certidão" : "Nova Certidão"}</h2>
              <button onClick={() => setModal(null)} className="p-1 hover:bg-muted rounded-md"><X className="w-4 h-4" /></button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Nome *</label>
                <input value={form.nome} onChange={e => setForm(f => ({...f, nome: e.target.value}))}
                  className="w-full border border-input bg-background rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  placeholder="Ex: CND Receita Federal" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">Tipo</label>
                  <select value={form.tipo} onChange={e => setForm(f => ({...f, tipo: e.target.value}))}
                    className="w-full border border-input bg-background rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary">
                    {TIPOS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Órgão Emissor</label>
                  <input value={form.orgaoEmissor} onChange={e => setForm(f => ({...f, orgaoEmissor: e.target.value}))}
                    className="w-full border border-input bg-background rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    placeholder="Ex: Receita Federal" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Número / Código</label>
                <input value={form.numero} onChange={e => setForm(f => ({...f, numero: e.target.value}))}
                  className="w-full border border-input bg-background rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary"
                  placeholder="Número da certidão" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">Data de Emissão</label>
                  <input type="date" value={form.dataEmissao} onChange={e => setForm(f => ({...f, dataEmissao: e.target.value}))}
                    className="w-full border border-input bg-background rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Data de Vencimento</label>
                  <input type="date" value={form.dataVencimento} onChange={e => setForm(f => ({...f, dataVencimento: e.target.value}))}
                    className="w-full border border-input bg-background rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Observações</label>
                <textarea value={form.descricao} onChange={e => setForm(f => ({...f, descricao: e.target.value}))}
                  rows={2} className="w-full border border-input bg-background rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                  placeholder="Notas adicionais..." />
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button onClick={() => setModal(null)} className="px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-muted transition-colors">Cancelar</button>
              <button
                onClick={handleSubmit}
                disabled={!form.nome || criar.isPending || atualizar.isPending}
                className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                {criar.isPending || atualizar.isPending ? "Salvando..." : typeof modal === "number" ? "Salvar" : "Criar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
