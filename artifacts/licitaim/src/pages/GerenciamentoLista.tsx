import React, { useState, useEffect } from "react";
import { Link, useLocation } from "wouter";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ClipboardList, Plus, Search, CheckCircle2, Clock, AlertTriangle,
  Trophy, XCircle, ChevronRight, Trash2, Filter, TrendingUp,
  Building2, MapPin, Calendar, Loader2, FolderOpen, Bell, FileWarning,
} from "lucide-react";
import { fmtDateBRT, fmtDateTime } from "../lib/dateUtils";
import { apiFetch } from "@/lib/apiFetch";
import { PageErrorState } from "@/components/PageErrorState";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

interface GerItem {
  id: number;
  licitacaoId: string;
  licitacaoNumero?: string;
  licitacaoObjeto?: string;
  licitacaoOrgao?: string;
  licitacaoUf?: string;
  licitacaoMunicipio?: string;
  licitacaoModalidade?: string;
  licitacaoSituacao?: string;
  licitacaoValor?: string;
  licitacaoDataEncerramento?: string;
  status: "em_andamento" | "finalizada" | "cancelada";
  resultado?: "ganhou" | "perdeu" | "desistiu" | null;
  totalTarefas: number;
  tarefasConcluidas: number;
  totalAnotacoes: number;
  docsPendentes: number;
  criadoEm: string;
  atualizadoEm: string;
}

const STATUS_CFG = {
  em_andamento: { label: "Em Andamento", cls: "bg-blue-500/10 text-blue-600 border-blue-500/20", icon: Clock },
  finalizada:   { label: "Finalizada",   cls: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20", icon: CheckCircle2 },
  cancelada:    { label: "Cancelada",    cls: "bg-rose-500/10 text-rose-600 border-rose-500/20", icon: XCircle },
} as const;

const RESULTADO_CFG = {
  ganhou:  { label: "Ganhou",  cls: "text-emerald-600 bg-emerald-50 border-emerald-200",  icon: Trophy },
  perdeu:  { label: "Perdeu",  cls: "text-rose-600 bg-rose-50 border-rose-200",           icon: XCircle },
  desistiu:{ label: "Desistiu",cls: "text-amber-600 bg-amber-50 border-amber-200",         icon: AlertTriangle },
} as const;

function fmtValor(v?: string | null) {
  if (!v) return null;
  const n = parseFloat(v);
  if (isNaN(n)) return v;
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function ProgressBar({ total, done }: { total: number; done: number }) {
  const pct = total === 0 ? 0 : Math.round((done / total) * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-primary rounded-full transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-muted-foreground w-12 text-right">{done}/{total}</span>
    </div>
  );
}

export default function GerenciamentoLista() {
  const qc = useQueryClient();
  const [location] = useLocation();
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState<string>("todos");
  const [filterDocsPendentes, setFilterDocsPendentes] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  // Refetch badge counts whenever the user navigates back to this list page.
  // The detail page marks alerts as read on mount and invalidates this query,
  // but since the list stays mounted in a SPA, we need an explicit refetch
  // triggered by the location change.
  useEffect(() => {
    qc.invalidateQueries({ queryKey: ["alertas-por-gerenciamento"] });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location]);

  const { data, isLoading, isError, error, refetch } = useQuery<{ data: GerItem[]; total: number }>({
    queryKey: ["gerenciamento"],
    queryFn: async () => {
      const res = await apiFetch(`${BASE}/api/gerenciamento`, { credentials: "include" });
      if (!res.ok) throw new Error("Erro ao carregar");
      return res.json();
    },
  });

  const { data: alertasData } = useQuery<{ data: Record<string, number> }>({
    queryKey: ["alertas-por-gerenciamento"],
    queryFn: async () => {
      const res = await apiFetch(`${BASE}/api/alertas/por-gerenciamento`, { credentials: "include" });
      if (!res.ok) throw new Error("Erro ao carregar alertas");
      return res.json();
    },
    refetchInterval: 60_000,
  });

  const alertasPorGer = alertasData?.data ?? {};

  const deleteMut = useMutation({
    mutationFn: async (id: number) => {
      const res = await apiFetch(`${BASE}/api/gerenciamento/${id}`, {
        method: "DELETE", credentials: "include",
      });
      if (!res.ok && res.status !== 204) throw new Error("Erro ao remover");
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["gerenciamento"] });
      setConfirmDelete(null);
    },
  });

  const items = (data?.data ?? []).filter(g => {
    const matchStatus = filterStatus === "todos" || g.status === filterStatus;
    const q = search.toLowerCase();
    const matchSearch = !q
      || g.licitacaoObjeto?.toLowerCase().includes(q)
      || g.licitacaoOrgao?.toLowerCase().includes(q)
      || g.licitacaoNumero?.toLowerCase().includes(q);
    const matchDocs = !filterDocsPendentes || (g.docsPendentes ?? 0) > 0;
    return matchStatus && matchSearch && matchDocs;
  });

  // Métricas
  const all = data?.data ?? [];
  const emAndamento = all.filter(g => g.status === "em_andamento").length;
  const finalizadas = all.filter(g => g.status === "finalizada").length;
  const ganhou = all.filter(g => g.resultado === "ganhou").length;
  const tarefasPendentes = all.reduce((s, g) => s + (g.totalTarefas - g.tarefasConcluidas), 0);
  const docsPendentesTotal = all.reduce((s, g) => s + (g.docsPendentes ?? 0), 0);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-5 border-b border-border flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg">
              <ClipboardList className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-foreground">Licitações Gerenciadas</h1>
              <p className="text-sm text-muted-foreground mt-0.5">
                Acompanhe o andamento das licitações em participação
              </p>
            </div>
          </div>
        </div>

        {/* Métricas rápidas */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-5">
          {[
            { label: "Em andamento", value: emAndamento, icon: Clock,        cls: "text-blue-600"    },
            { label: "Finalizadas",  value: finalizadas, icon: CheckCircle2, cls: "text-emerald-600" },
            { label: "Ganhou",       value: ganhou,      icon: Trophy,       cls: "text-amber-600"   },
            { label: "Tarefas pendentes", value: tarefasPendentes, icon: AlertTriangle, cls: "text-rose-600" },
          ].map(m => (
            <div key={m.label} className="bg-muted/40 border border-border rounded-lg px-4 py-3 flex items-center gap-3">
              <m.icon className={`w-5 h-5 flex-shrink-0 ${m.cls}`} />
              <div>
                <div className="text-lg font-bold text-foreground">{m.value}</div>
                <div className="text-xs text-muted-foreground">{m.label}</div>
              </div>
            </div>
          ))}
          {/* Docs pendentes — clicável para ativar filtro */}
          <button
            onClick={() => setFilterDocsPendentes(v => !v)}
            className={`px-4 py-3 flex items-center gap-3 rounded-lg border transition-all text-left ${
              filterDocsPendentes
                ? "bg-amber-500/15 border-amber-500/50 ring-2 ring-amber-500/30"
                : "bg-muted/40 border-border hover:bg-amber-500/10 hover:border-amber-500/30"
            }`}
            title={filterDocsPendentes ? "Remover filtro de docs pendentes" : "Filtrar por docs pendentes"}
          >
            <FileWarning className={`w-5 h-5 flex-shrink-0 ${filterDocsPendentes ? "text-amber-500" : "text-amber-500"}`} />
            <div>
              <div className="text-lg font-bold text-foreground">{docsPendentesTotal}</div>
              <div className={`text-xs ${filterDocsPendentes ? "text-amber-600 font-medium" : "text-muted-foreground"}`}>
                Docs pendentes
              </div>
            </div>
          </button>
        </div>
      </div>

      {/* Filtros */}
      <div className="px-6 py-3 border-b border-border bg-muted/20 flex items-center gap-3 flex-shrink-0 flex-wrap">
        <div className="relative flex-1 min-w-48 max-w-sm">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Buscar por objeto, órgão ou número…"
            className="w-full pl-9 pr-3 py-1.5 text-sm border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0 flex-wrap">
          <Filter className="w-3.5 h-3.5 text-muted-foreground" />
          {["todos", "em_andamento", "finalizada", "cancelada"].map(s => (
            <button
              key={s}
              onClick={() => setFilterStatus(s)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                filterStatus === s
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              {s === "todos" ? "Todos" : s === "em_andamento" ? "Em andamento" : s === "finalizada" ? "Finalizadas" : "Canceladas"}
            </button>
          ))}
          <div className="w-px h-4 bg-border mx-1 flex-shrink-0" />
          <button
            onClick={() => setFilterDocsPendentes(v => !v)}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              filterDocsPendentes
                ? "bg-amber-500 text-white"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            <FileWarning className="w-3 h-3" />
            Docs pendentes
          </button>
        </div>
      </div>

      {/* Lista */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {isError ? (
          <PageErrorState error={error} onRetry={() => refetch()} />
        ) : isLoading ? (
          <div className="flex items-center justify-center py-16 gap-2 text-muted-foreground">
            <Loader2 className="w-5 h-5 animate-spin" />
            Carregando…
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="p-4 bg-muted/40 rounded-full mb-4">
              <FolderOpen className="w-10 h-10 text-muted-foreground" />
            </div>
            <h3 className="font-semibold text-foreground mb-1">
              {all.length === 0 ? "Nenhuma licitação gerenciada" : "Nenhum resultado"}
            </h3>
            <p className="text-sm text-muted-foreground max-w-sm">
              {all.length === 0
                ? 'Acesse a página de Licitações, encontre uma de interesse e clique em "Gerenciar Licitação".'
                : "Tente ajustar os filtros ou a busca."}
            </p>
            {all.length === 0 && (
              <Link href="/licitacoes"
                className="mt-4 flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors">
                <Search className="w-4 h-4" />
                Buscar Licitações
              </Link>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {items.map(g => {
              const stCfg = STATUS_CFG[g.status];
              const resCfg = g.resultado ? RESULTADO_CFG[g.resultado] : null;
              const diasEnc = g.licitacaoDataEncerramento
                ? Math.ceil((new Date(g.licitacaoDataEncerramento).getTime() - Date.now()) / 86400000)
                : null;

              return (
                <div key={g.id} className="bg-card border border-border rounded-xl hover:shadow-md transition-shadow group">
                  <div className="p-4">
                    <div className="flex items-start gap-3">
                      {/* Ícone status */}
                      <div className={`mt-0.5 p-1.5 rounded-lg border ${stCfg.cls} flex-shrink-0`}>
                        <stCfg.icon className="w-4 h-4" />
                      </div>

                      <div className="flex-1 min-w-0">
                        {/* Linha 1: número + badges */}
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          {g.licitacaoNumero && (
                            <span className="text-xs font-mono text-muted-foreground">{g.licitacaoNumero}</span>
                          )}
                          <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${stCfg.cls}`}>
                            {stCfg.label}
                          </span>
                          {alertasPorGer[String(g.id)] > 0 && (
                            <span
                              className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border font-semibold bg-rose-500/10 text-rose-600 border-rose-500/30"
                              title={`${alertasPorGer[String(g.id)]} alerta${alertasPorGer[String(g.id)] !== 1 ? "s" : ""} não lido${alertasPorGer[String(g.id)] !== 1 ? "s" : ""}`}
                            >
                              <Bell className="w-3 h-3" />
                              {alertasPorGer[String(g.id)]}
                            </span>
                          )}
                          {(g.docsPendentes ?? 0) > 0 && (
                            <span
                              className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border font-semibold bg-amber-500/10 text-amber-700 border-amber-500/30"
                              title={`${g.docsPendentes} documento${g.docsPendentes !== 1 ? "s" : ""} de habilitação pendente${g.docsPendentes !== 1 ? "s" : ""}`}
                            >
                              <FileWarning className="w-3 h-3" />
                              {g.docsPendentes} doc{g.docsPendentes !== 1 ? "s" : ""} pendente{g.docsPendentes !== 1 ? "s" : ""}
                            </span>
                          )}
                          {resCfg && (
                            <span className={`text-xs px-2 py-0.5 rounded-full border font-medium flex items-center gap-1 ${resCfg.cls}`}>
                              <resCfg.icon className="w-3 h-3" />
                              {resCfg.label}
                            </span>
                          )}
                          {g.licitacaoModalidade && (
                            <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                              {g.licitacaoModalidade}
                            </span>
                          )}
                        </div>

                        {/* Objeto */}
                        <p className="text-sm font-medium text-foreground line-clamp-2 mb-2">
                          {g.licitacaoObjeto || "Objeto não informado"}
                        </p>

                        {/* Meta info */}
                        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground mb-3">
                          {g.licitacaoOrgao && (
                            <span className="flex items-center gap-1">
                              <Building2 className="w-3 h-3" />
                              {g.licitacaoOrgao}
                            </span>
                          )}
                          {(g.licitacaoMunicipio || g.licitacaoUf) && (
                            <span className="flex items-center gap-1">
                              <MapPin className="w-3 h-3" />
                              {[g.licitacaoMunicipio, g.licitacaoUf].filter(Boolean).join("/")}
                            </span>
                          )}
                          {g.licitacaoDataEncerramento && (
                            <span className={`flex items-center gap-1 ${diasEnc !== null && diasEnc <= 3 && diasEnc >= 0 ? "text-rose-500 font-semibold" : ""}`}>
                              <Calendar className="w-3 h-3" />
                              Encerra: {fmtDateBRT(g.licitacaoDataEncerramento)}
                              {diasEnc !== null && diasEnc >= 0 && diasEnc <= 7 && (
                                <span className="ml-1 font-semibold">({diasEnc}d)</span>
                              )}
                            </span>
                          )}
                          {g.licitacaoValor && (
                            <span className="flex items-center gap-1 font-medium text-foreground">
                              <TrendingUp className="w-3 h-3 text-primary" />
                              {fmtValor(g.licitacaoValor)}
                            </span>
                          )}
                        </div>

                        {/* Progresso tarefas */}
                        {g.totalTarefas > 0 && (
                          <div className="mb-3">
                            <div className="text-xs text-muted-foreground mb-1">
                              Tarefas — {g.tarefasConcluidas}/{g.totalTarefas} concluídas
                            </div>
                            <ProgressBar total={g.totalTarefas} done={g.tarefasConcluidas} />
                          </div>
                        )}

                        {/* Contadores + ações */}
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
                            <span>{g.totalTarefas} tarefa{g.totalTarefas !== 1 ? "s" : ""}</span>
                            <span>·</span>
                            <span>{g.totalAnotacoes} anotaç{g.totalAnotacoes !== 1 ? "ões" : "ão"}</span>
                            <span>·</span>
                            <span>Gerenciada desde {fmtDateBRT(g.criadoEm)}</span>
                          </div>

                          <div className="flex items-center gap-2">
                            {/* Remover */}
                            {confirmDelete === g.id ? (
                              <div className="flex items-center gap-1.5">
                                <span className="text-xs text-muted-foreground">Confirmar?</span>
                                <button
                                  onClick={() => deleteMut.mutate(g.id)}
                                  disabled={deleteMut.isPending}
                                  className="px-2 py-1 text-xs bg-destructive text-destructive-foreground rounded-md hover:bg-destructive/90 transition-colors"
                                >
                                  {deleteMut.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : "Sim"}
                                </button>
                                <button
                                  onClick={() => setConfirmDelete(null)}
                                  className="px-2 py-1 text-xs border border-border rounded-md hover:bg-muted transition-colors"
                                >
                                  Não
                                </button>
                              </div>
                            ) : (
                              <button
                                onClick={() => setConfirmDelete(g.id)}
                                className="p-1.5 rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors opacity-0 group-hover:opacity-100"
                                title="Remover do gerenciamento"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            )}

                            {/* Acessar */}
                            <Link
                              href={`/gerenciamento/${g.id}`}
                              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors"
                            >
                              Acessar
                              <ChevronRight className="w-3.5 h-3.5" />
                            </Link>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
