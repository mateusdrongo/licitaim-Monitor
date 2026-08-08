import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "wouter";
import {
  CalendarDays,
  Clock,
  FileCheck2,
  Bell,
  ChevronRight,
  CheckCircle2,
  Plus,
  X,
  Trash2,
  CalendarPlus,
} from "lucide-react";
import { apiFetch } from "@/lib/apiFetch";
import { PageErrorState } from "@/components/PageErrorState";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

interface Evento {
  id: string;
  titulo: string;
  data: string;
  tipo: string;
  status: string;
  urgencia: "normal" | "atencao" | "critico";
  link?: string;
  descricao?: string;
  evento_id?: number;
}

interface AgendaData {
  eventos: Evento[];
  resumo: { total: number; criticos: number; atencao: number; proximos7dias: number };
}

function useAgenda() {
  return useQuery<AgendaData>({
    queryKey: ["agenda"],
    queryFn: async () => {
      const res = await apiFetch(`${BASE}/api/agenda`, { credentials: "include" });
      if (!res.ok) throw new Error("Erro ao buscar agenda");
      return res.json();
    },
  });
}

const tipoConfig: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
  prazo_oportunidade: { icon: <Clock className="w-4 h-4" />, label: "Oportunidade", color: "text-blue-500 bg-blue-500/10" },
  oportunidade:       { icon: <Clock className="w-4 h-4" />, label: "Oportunidade", color: "text-blue-500 bg-blue-500/10" },
  prazo_certidao:     { icon: <FileCheck2 className="w-4 h-4" />, label: "Certidão",    color: "text-purple-500 bg-purple-500/10" },
  certidao:           { icon: <FileCheck2 className="w-4 h-4" />, label: "Certidão",    color: "text-purple-500 bg-purple-500/10" },
  alerta:             { icon: <Bell className="w-4 h-4" />, label: "Alerta",       color: "text-amber-500 bg-amber-500/10" },
  favorito:           { icon: <CheckCircle2 className="w-4 h-4" />, label: "Favorito",  color: "text-emerald-500 bg-emerald-500/10" },
  evento:             { icon: <CalendarPlus className="w-4 h-4" />, label: "Evento",    color: "text-pink-500 bg-pink-500/10" },
};

const TIPO_FALLBACK = { icon: <Bell className="w-4 h-4" />, label: "Evento", color: "text-muted-foreground bg-muted" };

const urgenciaConfig = {
  critico: "border-l-4 border-l-red-500 bg-red-500/5",
  atencao: "border-l-4 border-l-amber-500 bg-amber-500/5",
  normal:  "border-l-4 border-l-border",
};

const urgenciaLabel = {
  critico: { label: "Crítico", cls: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" },
  atencao: { label: "Atenção", cls: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" },
  normal:  { label: "Normal",  cls: "bg-muted text-muted-foreground" },
};

// ─── Formulário de criação de evento ─────────────────────────────────────────
interface EventoForm {
  titulo: string;
  data: string;
  descricao: string;
  observacao: string;
}

function NovoEventoModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState<EventoForm>({
    titulo: "",
    data: new Date().toISOString().slice(0, 10),
    descricao: "",
    observacao: "",
  });
  const [error, setError] = useState("");

  const mutation = useMutation({
    mutationFn: async (data: EventoForm) => {
      const res = await apiFetch(`${BASE}/api/agenda/eventos`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          titulo:     data.titulo.trim(),
          data:       data.data,
          descricao:  data.descricao.trim() || null,
          observacao: data.observacao.trim() || null,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Erro ao criar evento");
      }
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agenda"] });
      onClose();
    },
    onError: (e: Error) => setError(e.message),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!form.titulo.trim()) { setError("O título é obrigatório."); return; }
    if (!form.data)           { setError("A data é obrigatória."); return; }
    mutation.mutate(form);
  };

  const field = (label: string, required = false) => (
    <span className="text-sm font-medium text-foreground">
      {label}{required && <span className="text-red-500 ml-0.5">*</span>}
    </span>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-md bg-card border border-border rounded-2xl shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <CalendarPlus className="w-5 h-5 text-primary" />
            Novo Evento
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-muted transition-colors text-muted-foreground"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Título */}
          <div className="space-y-1.5">
            {field("Título", true)}
            <input
              type="text"
              value={form.titulo}
              onChange={e => setForm(f => ({ ...f, titulo: e.target.value }))}
              placeholder="Ex: Reunião de qualificação técnica"
              maxLength={120}
              className="w-full px-3 py-2 text-sm bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 placeholder:text-muted-foreground"
            />
          </div>

          {/* Data */}
          <div className="space-y-1.5">
            {field("Data", true)}
            <input
              type="date"
              value={form.data}
              onChange={e => setForm(f => ({ ...f, data: e.target.value }))}
              className="w-full px-3 py-2 text-sm bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>

          {/* Descrição */}
          <div className="space-y-1.5">
            {field("Descrição")}
            <textarea
              value={form.descricao}
              onChange={e => setForm(f => ({ ...f, descricao: e.target.value }))}
              placeholder="Detalhes do evento (opcional)"
              rows={2}
              maxLength={400}
              className="w-full px-3 py-2 text-sm bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none placeholder:text-muted-foreground"
            />
          </div>

          {/* Observação */}
          <div className="space-y-1.5">
            {field("Observação")}
            <textarea
              value={form.observacao}
              onChange={e => setForm(f => ({ ...f, observacao: e.target.value }))}
              placeholder="Notas internas, lembretes, links... (opcional)"
              rows={2}
              maxLength={400}
              className="w-full px-3 py-2 text-sm bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none placeholder:text-muted-foreground"
            />
          </div>

          {/* Error */}
          {error && (
            <p className="text-sm text-red-600 bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded-lg">
              {error}
            </p>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 text-sm font-medium bg-muted text-muted-foreground rounded-lg hover:bg-muted/80 transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="flex-1 px-4 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-60"
            >
              {mutation.isPending ? "Salvando…" : "Criar Evento"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Exclusão de eventos personalizados ──────────────────────────────────────
function useDeleteEvento() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (eventoId: number) => {
      const res = await apiFetch(`${BASE}/api/agenda/eventos/${eventoId}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok && res.status !== 204) throw new Error("Erro ao excluir");
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agenda"] }),
  });
}

// ─── Página ───────────────────────────────────────────────────────────────────
export default function Agenda() {
  const { data, isLoading, isError, error, refetch } = useAgenda();
  const [filtro, setFiltro] = useState<"todos" | "critico" | "atencao">("todos");
  const [showModal, setShowModal] = useState(false);
  const deleteEvento = useDeleteEvento();

  const eventos = data?.eventos?.filter((e) => {
    if (filtro === "critico") return e.urgencia === "critico";
    if (filtro === "atencao") return e.urgencia === "atencao" || e.urgencia === "critico";
    return true;
  }) ?? [];

  const hoje = new Date();
  const prox7  = eventos.filter(e => { const d = new Date(e.data); const diff = Math.ceil((d.getTime() - hoje.getTime()) / 86400000); return diff >= 0 && diff <= 7; });
  const prox30 = eventos.filter(e => { const d = new Date(e.data); const diff = Math.ceil((d.getTime() - hoje.getTime()) / 86400000); return diff > 7 && diff <= 30; });
  const vencidos = eventos.filter(e => new Date(e.data) < hoje);
  const mais30   = eventos.filter(e => { const d = new Date(e.data); const diff = Math.ceil((d.getTime() - hoje.getTime()) / 86400000); return diff > 30; });

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "short" });

  const diffDias = (iso: string) => {
    const d = new Date(iso);
    const diff = Math.ceil((d.getTime() - hoje.getTime()) / 86400000);
    if (diff < 0) return `${Math.abs(diff)}d atrás`;
    if (diff === 0) return "Hoje";
    if (diff === 1) return "Amanhã";
    return `em ${diff}d`;
  };

  const EventoCard = ({ evento }: { evento: Evento }) => {
    const tipo = tipoConfig[evento.tipo] ?? TIPO_FALLBACK;
    const urg  = urgenciaLabel[evento.urgencia];
    const isCustom = evento.tipo === "evento" && evento.evento_id != null;

    const card = (
      <div className={`p-4 rounded-xl bg-card border border-border shadow-sm ${urgenciaConfig[evento.urgencia] ?? urgenciaConfig.normal} flex gap-4 items-start group hover:shadow-md transition-shadow`}>
        <div className={`p-2 rounded-lg ${tipo.color} mt-0.5 shrink-0`}>
          {tipo.icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-medium text-sm truncate pr-2">{evento.titulo}</h3>
            <div className="flex items-center gap-2 shrink-0">
              <span className={`text-xs font-mono font-semibold px-2 py-0.5 rounded ${urg.cls}`}>
                {diffDias(evento.data)}
              </span>
              {isCustom && (
                <button
                  onClick={e => { e.preventDefault(); e.stopPropagation(); deleteEvento.mutate(evento.evento_id!); }}
                  className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-muted-foreground hover:text-red-600"
                  title="Excluir evento"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${tipo.color}`}>{tipo.label}</span>
            <span className="text-xs text-muted-foreground">{formatDate(evento.data)}</span>
            {evento.descricao && <span className="text-xs text-muted-foreground truncate max-w-xs">· {evento.descricao}</span>}
          </div>
        </div>
        {evento.link && <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0 mt-1 opacity-0 group-hover:opacity-100 transition-opacity" />}
      </div>
    );
    return evento.link ? <Link href={evento.link}>{card}</Link> : card;
  };

  const Section = ({ title, items }: { title: string; items: Evento[] }) => {
    if (items.length === 0) return null;
    return (
      <div className="space-y-2">
        <h2 className="text-xs font-bold uppercase tracking-widest text-muted-foreground px-1">{title}</h2>
        {items.map(e => <EventoCard key={e.id} evento={e} />)}
      </div>
    );
  };

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8">
      {showModal && <NovoEventoModal onClose={() => setShowModal(false)} />}

      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <CalendarDays className="w-8 h-8 text-primary" /> Agenda de Prazos
          </h1>
          <p className="text-muted-foreground mt-1">Prazos de oportunidades, certidões e alertas críticos.</p>
        </div>

        <div className="flex gap-2 flex-wrap">
          {(["todos", "critico", "atencao"] as const).map(f => (
            <button
              key={f}
              onClick={() => setFiltro(f)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                filtro === f ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              {f === "todos" ? "Todos" : f === "critico" ? "🔴 Críticos" : "🟡 Atenção"}
            </button>
          ))}
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Novo Evento
          </button>
        </div>
      </div>

      {/* Summary cards */}
      {data?.resumo && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: "Total de eventos",  value: data.resumo.total,         cls: "text-foreground" },
            { label: "Críticos",          value: data.resumo.criticos,       cls: "text-red-600"    },
            { label: "Atenção",           value: data.resumo.atencao,        cls: "text-amber-600"  },
            { label: "Próximos 7 dias",   value: data.resumo.proximos7dias,  cls: "text-primary"    },
          ].map(stat => (
            <div key={stat.label} className="bg-card border border-border rounded-xl p-4 text-center">
              <div className={`text-2xl font-bold font-mono ${stat.cls}`}>{stat.value}</div>
              <div className="text-xs text-muted-foreground mt-1">{stat.label}</div>
            </div>
          ))}
        </div>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {[1,2,3,4,5].map(i => <div key={i} className="h-20 bg-muted animate-pulse rounded-xl" />)}
        </div>
      ) : isError ? (
        <PageErrorState error={error} onRetry={() => refetch()} />
      ) : eventos.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <CalendarDays className="w-12 h-12 text-muted-foreground mb-4 opacity-50" />
          <h3 className="font-semibold text-lg">Agenda limpa</h3>
          <p className="text-muted-foreground text-sm mt-1">
            Nenhum prazo nos próximos 60 dias. Adicione oportunidades com prazo, cadastre certidões ou crie um evento.
          </p>
          <div className="flex gap-3 mt-6">
            <Link href="/oportunidades" className="text-sm font-medium text-primary hover:underline">Ver Pipeline →</Link>
            <Link href="/certidoes"     className="text-sm font-medium text-primary hover:underline">Certidões →</Link>
            <button onClick={() => setShowModal(true)} className="text-sm font-medium text-primary hover:underline">
              + Criar Evento
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-8">
          {vencidos.length > 0  && <Section title="Vencidos / Em atraso"  items={vencidos} />}
          <Section title="Próximos 7 dias"  items={prox7}  />
          <Section title="Próximos 30 dias" items={prox30} />
          {mais30.length > 0    && <Section title="Mais de 30 dias"       items={mais30} />}
        </div>
      )}
    </div>
  );
}
