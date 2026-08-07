import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "wouter";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import {
  TrendingUp,
  Trophy,
  Target,
  Percent,
  AlertTriangle,
  ChevronRight,
  BarChart3,
} from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

interface AnalyticsData {
  taxaVitoria: number;
  ganhou: number;
  perdeu: number;
  valorGanho: number;
  valorPipelineAtivo: number;
  valorPonderado: number;
  totalOportunidades: number;
  pipelinePorEstagio: { estagio: string; quantidade: number; valor: number }[];
  certidoesAlerta: { id: number; nome: string; dataVencimento: string | null; diasRestantes: number }[];
  alertasPorTipo: { tipo: string; total: number; naoLidos: number }[];
  monitoramentosTop: { id: number; nome: string; ativo: boolean; totalAlertas: number }[];
}

function useAnalytics() {
  return useQuery<AnalyticsData>({
    queryKey: ["analytics"],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/analytics`, { credentials: "include" });
      if (!res.ok) throw new Error("Erro");
      return res.json();
    },
  });
}

const fmt = (v: number) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v);
const fmtK = (v: number) => v >= 1_000_000 ? `R$ ${(v / 1_000_000).toFixed(1)}M` : v >= 1_000 ? `R$ ${(v / 1_000).toFixed(0)}K` : fmt(v);

const estagioLabels: Record<string, string> = {
  identificada: "Identificada", qualificada: "Qualificada", proposta: "Proposta",
  disputa: "Disputa", ganhou: "Ganhou", perdeu: "Perdeu",
};

const estagioColors: Record<string, string> = {
  identificada: "#6366f1", qualificada: "#8b5cf6", proposta: "#3b82f6",
  disputa: "#f59e0b", ganhou: "#10b981", perdeu: "#ef4444",
};

const tipoAlertaLabels: Record<string, string> = {
  nova_licitacao: "Nova licitação",
  prazo_vencendo: "Prazo vencendo",
  situacao_alterada: "Sit. alterada",
  nova_disputa: "Nova disputa",
  preco_referencia: "Preço ref.",
};

export default function Analytics() {
  const { data, isLoading } = useAnalytics();

  if (isLoading) return (
    <div className="p-8 space-y-6">
      <div className="h-8 w-48 bg-muted animate-pulse rounded" />
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[1,2,3,4].map(i => <div key={i} className="h-28 bg-muted animate-pulse rounded-xl" />)}
      </div>
    </div>
  );

  if (!data) return null;

  const pipelineChartData = data.pipelinePorEstagio
    .filter((e) => e.quantidade > 0)
    .map((e) => ({ ...e, label: estagioLabels[e.estagio] ?? e.estagio }));

  const alertasChartData = data.alertasPorTipo.filter((a) => a.total > 0);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
          <BarChart3 className="w-8 h-8 text-primary" /> Inteligência Comercial
        </h1>
        <p className="text-muted-foreground mt-1">Análise de desempenho, pipeline e compliance.</p>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-card border border-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Taxa de Vitória</span>
            <div className="p-2 bg-emerald-500/10 text-emerald-600 rounded-md"><Percent className="w-4 h-4" /></div>
          </div>
          <div className="text-3xl font-bold font-mono text-emerald-600">{data.taxaVitoria}%</div>
          <div className="text-xs text-muted-foreground mt-1">{data.ganhou} ganhos · {data.perdeu} perdidos</div>
        </div>

        <div className="bg-card border border-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Valor Ganho</span>
            <div className="p-2 bg-primary/10 text-primary rounded-md"><Trophy className="w-4 h-4" /></div>
          </div>
          <div className="text-2xl font-bold font-mono text-primary">{fmtK(data.valorGanho)}</div>
          <div className="text-xs text-muted-foreground mt-1">Contratos adjudicados</div>
        </div>

        <div className="bg-card border border-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Pipeline Ativo</span>
            <div className="p-2 bg-blue-500/10 text-blue-600 rounded-md"><TrendingUp className="w-4 h-4" /></div>
          </div>
          <div className="text-2xl font-bold font-mono text-blue-600">{fmtK(data.valorPipelineAtivo)}</div>
          <div className="text-xs text-muted-foreground mt-1">{data.totalOportunidades} oportunidades</div>
        </div>

        <div className="bg-card border border-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Valor Esperado</span>
            <div className="p-2 bg-purple-500/10 text-purple-600 rounded-md"><Target className="w-4 h-4" /></div>
          </div>
          <div className="text-2xl font-bold font-mono text-purple-600">{fmtK(data.valorPonderado)}</div>
          <div className="text-xs text-muted-foreground mt-1">Prob. ponderada</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Pipeline by stage */}
        <div className="bg-card border border-border rounded-xl p-6 space-y-4">
          <h2 className="font-semibold text-sm flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-muted-foreground" /> Pipeline por Estágio
          </h2>
          {pipelineChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={pipelineChartData} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
                <XAxis dataKey="label" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} width={30} />
                <Tooltip
                  formatter={(v: number, name: string) => [name === "valor" ? fmtK(v) : v, name === "valor" ? "Valor" : "Qtd."]}
                  contentStyle={{ fontSize: 12, borderRadius: 8 }}
                />
                <Bar dataKey="quantidade" radius={4}>
                  {pipelineChartData.map((e) => (
                    <Cell key={e.estagio} fill={estagioColors[e.estagio] ?? "#6366f1"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-sm text-muted-foreground">
              Nenhuma oportunidade cadastrada. <Link href="/oportunidades" className="ml-1 text-primary hover:underline">Criar →</Link>
            </div>
          )}
        </div>

        {/* Alerts by type */}
        <div className="bg-card border border-border rounded-xl p-6 space-y-4">
          <h2 className="font-semibold text-sm flex items-center gap-2">
            <Target className="w-4 h-4 text-muted-foreground" /> Alertas por Tipo
          </h2>
          {alertasChartData.length > 0 ? (
            <div className="space-y-3">
              {alertasChartData.map((a) => (
                <div key={a.tipo} className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground w-28 shrink-0">{tipoAlertaLabels[a.tipo] ?? a.tipo}</span>
                  <div className="flex-1 bg-muted rounded-full h-2 overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full transition-all"
                      style={{ width: `${(a.total / Math.max(...alertasChartData.map(x => x.total))) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono font-semibold w-6 text-right">{a.total}</span>
                  {a.naoLidos > 0 && (
                    <span className="text-xs bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 px-1.5 py-0.5 rounded font-medium">{a.naoLidos} new</span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="h-[180px] flex items-center justify-center text-sm text-muted-foreground">Sem alertas gerados ainda.</div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Certidões vencendo */}
        <div className="bg-card border border-border rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-sm flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-500" /> Certidões Vencendo
            </h2>
            <Link href="/certidoes" className="text-xs text-primary hover:underline flex items-center gap-1">
              Gerenciar <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
          {data.certidoesAlerta.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              Nenhuma certidão vencendo em 30 dias. <Link href="/certidoes" className="text-primary hover:underline">Cadastrar →</Link>
            </div>
          ) : (
            <div className="space-y-2">
              {data.certidoesAlerta.map((c) => (
                <div key={c.id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                  <span className="text-sm font-medium truncate pr-4">{c.nome}</span>
                  <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded whitespace-nowrap ${
                    c.diasRestantes < 0 ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                    : c.diasRestantes <= 7 ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                    : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
                  }`}>
                    {c.diasRestantes < 0 ? `${Math.abs(c.diasRestantes)}d vencida` : `${c.diasRestantes}d`}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Top monitoramentos */}
        <div className="bg-card border border-border rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-sm flex items-center gap-2">
              <Target className="w-4 h-4 text-primary" /> Monitoramentos Mais Ativos
            </h2>
            <Link href="/monitoramentos" className="text-xs text-primary hover:underline flex items-center gap-1">
              Ver todos <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
          {data.monitoramentosTop.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              Nenhum monitoramento. <Link href="/monitoramentos" className="text-primary hover:underline">Criar →</Link>
            </div>
          ) : (
            <div className="space-y-2">
              {data.monitoramentosTop.map((m) => (
                <div key={m.id} className="flex items-center gap-3 py-2 border-b border-border last:border-0">
                  <div className={`w-2 h-2 rounded-full shrink-0 ${m.ativo ? "bg-emerald-500" : "bg-muted-foreground"}`} />
                  <span className="text-sm flex-1 truncate">{m.nome}</span>
                  <span className="text-xs font-mono font-semibold text-muted-foreground">{m.totalAlertas} alertas</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
