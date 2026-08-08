import React, { useState, useMemo, useRef, useEffect } from "react";
import { useGetDashboard } from "@workspace/api-client-react";
import { useQuery } from "@tanstack/react-query";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import {
  BarChart3,
  Target,
  AlertCircle,
  Briefcase,
  FileText,
  Clock,
  ChevronRight,
  ChevronLeft,
  Star,
  TrendingUp,
  Zap,
  Timer,
  Bell,
  ShieldAlert,
  FileMinus,
  MapPin,
  CalendarDays,
  X,
} from "lucide-react";
import { Link } from "wouter";
import { apiFetch } from "@/lib/apiFetch";
import { PageErrorState } from "@/components/PageErrorState";
import { CollectorStatusCard } from "@/components/CollectorStatusCard";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

// ─── UF names & palette ───────────────────────────────────────────────────────
const UF_NAMES: Record<string, string> = {
  AC:"Acre", AL:"Alagoas", AM:"Amazonas", AP:"Amapá", BA:"Bahia",
  CE:"Ceará", DF:"Distrito Federal", ES:"Espírito Santo", GO:"Goiás",
  MA:"Maranhão", MG:"Minas Gerais", MS:"Mato Grosso do Sul", MT:"Mato Grosso",
  PA:"Pará", PB:"Paraíba", PE:"Pernambuco", PI:"Piauí", PR:"Paraná",
  RJ:"Rio de Janeiro", RN:"Rio Grande do Norte", RO:"Rondônia", RR:"Roraima",
  RS:"Rio Grande do Sul", SC:"Santa Catarina", SE:"Sergipe", SP:"São Paulo",
  TO:"Tocantins",
};

// 27 visually distinct colours
const UF_COLORS = [
  "#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6",
  "#06b6d4","#f97316","#84cc16","#ec4899","#14b8a6",
  "#6366f1","#eab308","#22c55e","#a855f7","#0ea5e9",
  "#fb923c","#4ade80","#f43f5e","#2dd4bf","#818cf8",
  "#fbbf24","#34d399","#c084fc","#38bdf8","#fb7185",
  "#a3e635","#fdba74",
];

// Custom tooltip rendered by Recharts
function UfTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const { uf, total } = payload[0].payload;
  return (
    <div className="bg-popover border border-border rounded-lg shadow-lg px-3 py-2 text-sm">
      <p className="font-semibold">{UF_NAMES[uf] ?? uf} <span className="font-mono text-xs text-muted-foreground">({uf})</span></p>
      <p className="text-muted-foreground text-xs mt-0.5">
        {total.toLocaleString("pt-BR")} licitação{total !== 1 ? "ões" : ""}
      </p>
    </div>
  );
}

// ─── Pie chart "Licitações por Estado" ────────────────────────────────────────
interface UfPieChartProps {
  data: Array<{ uf: string; total: number; monitorado: boolean }>;
}

function UfPieChart({ data }: UfPieChartProps) {
  const [active, setActive] = useState<number | null>(null);

  return (
    <div className="flex flex-col gap-4">
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={data}
            dataKey="total"
            nameKey="uf"
            cx="50%"
            cy="50%"
            innerRadius="48%"
            outerRadius="78%"
            paddingAngle={1.5}
            strokeWidth={0}
            onMouseEnter={(_, idx) => setActive(idx)}
            onMouseLeave={() => setActive(null)}
          >
            {data.map((entry, idx) => (
              <Cell
                key={entry.uf}
                fill={UF_COLORS[idx % UF_COLORS.length]}
                opacity={active === null || active === idx ? 1 : 0.45}
                stroke={active === idx ? "#fff" : "transparent"}
                strokeWidth={active === idx ? 1.5 : 0}
                style={{ cursor: "pointer", transition: "opacity 0.15s" }}
              />
            ))}
          </Pie>
          <Tooltip content={<UfTooltip />} />
        </PieChart>
      </ResponsiveContainer>

      {/* Colour legend — compact grid */}
      <div className="grid grid-cols-3 gap-x-4 gap-y-1.5">
        {data.map((item, idx) => (
          <div
            key={item.uf}
            className="flex items-center gap-1.5 text-[11px] cursor-default"
            onMouseEnter={() => setActive(idx)}
            onMouseLeave={() => setActive(null)}
          >
            <span
              className="inline-block w-2.5 h-2.5 rounded-sm flex-shrink-0"
              style={{ backgroundColor: UF_COLORS[idx % UF_COLORS.length] }}
            />
            <span className={`font-mono font-bold ${active === idx ? "text-foreground" : "text-muted-foreground"}`}>
              {item.uf}
            </span>
            {item.monitorado && (
              <span title="Monitorado" className="w-1.5 h-1.5 rounded-full bg-primary flex-shrink-0" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Mini-Calendar ────────────────────────────────────────────────────────────
const WEEKDAYS = ["D", "S", "T", "Q", "Q", "S", "S"];
const MONTHS = [
  "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
  "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro",
];

interface CalendarEvent {
  data: string;
  urgencia: "critico" | "atencao" | "normal";
}

interface MiniCalendarProps {
  events: CalendarEvent[];
  selected: string; // ISO date
  onSelect: (iso: string) => void;
}

function MiniCalendar({ events, selected, onSelect }: MiniCalendarProps) {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());

  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  // Map date string → urgency colour
  const eventMap = useMemo(() => {
    const m: Record<string, "critico" | "atencao" | "normal"> = {};
    for (const ev of events) {
      const d = ev.data.slice(0, 10);
      const [ey, em, ed] = d.split("-").map(Number);
      if (ey === year && em - 1 === month) {
        const prev = m[d];
        if (!prev || ev.urgencia === "critico" || (ev.urgencia === "atencao" && prev === "normal")) {
          m[d] = ev.urgencia;
        }
      }
    }
    return m;
  }, [events, year, month]);

  const prevMonth = () => {
    if (month === 0) { setMonth(11); setYear(y => y - 1); }
    else setMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (month === 11) { setMonth(0); setYear(y => y + 1); }
    else setMonth(m => m + 1);
  };

  const todayIso = today.toISOString().slice(0, 10);

  const cells: (number | null)[] = [
    ...Array(firstDay).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];

  // Pad to full weeks
  while (cells.length % 7 !== 0) cells.push(null);

  return (
    <div className="select-none">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <button onClick={prevMonth} className="p-1 rounded hover:bg-muted transition-colors">
          <ChevronLeft className="w-4 h-4" />
        </button>
        <span className="text-sm font-semibold">{MONTHS[month]} {year}</span>
        <button onClick={nextMonth} className="p-1 rounded hover:bg-muted transition-colors">
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
      {/* Weekday headers */}
      <div className="grid grid-cols-7 mb-1">
        {WEEKDAYS.map((d, i) => (
          <div key={i} className="text-center text-[10px] font-medium text-muted-foreground py-0.5">{d}</div>
        ))}
      </div>
      {/* Days */}
      <div className="grid grid-cols-7 gap-y-0.5">
        {cells.map((day, i) => {
          if (!day) return <div key={i} />;
          const iso = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
          const isToday = iso === todayIso;
          const isSelected = iso === selected;
          const urgency = eventMap[iso];
          const dotColor =
            urgency === "critico" ? "bg-red-500" :
            urgency === "atencao" ? "bg-amber-400" :
            urgency === "normal"  ? "bg-emerald-500" : "";

          return (
            <button
              key={i}
              onClick={() => onSelect(iso)}
              className={`relative flex flex-col items-center py-1 rounded-md text-xs font-medium transition-colors
                ${isSelected ? "bg-primary text-primary-foreground" :
                  isToday ? "bg-primary/10 text-primary" :
                  "hover:bg-muted text-foreground"}`}
            >
              {day}
              {urgency && (
                <span className={`absolute bottom-0.5 w-1 h-1 rounded-full ${dotColor} ${isSelected ? "opacity-80" : ""}`} />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
const formatCurrency = (value: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value);

const urgencyBadge = (urgencia: string) => {
  if (urgencia === "critico") return "bg-red-500/10 text-red-600 border-red-200";
  if (urgencia === "atencao") return "bg-amber-500/10 text-amber-600 border-amber-200";
  return "bg-emerald-500/10 text-emerald-600 border-emerald-200";
};

const urgencyLabel = (urgencia: string) => {
  if (urgencia === "critico") return "Crítico";
  if (urgencia === "atencao") return "Atenção";
  return "Normal";
};

const tipoIcon = (tipo: string) => {
  if (tipo === "certidao") return <ShieldAlert className="w-3.5 h-3.5" />;
  if (tipo === "oportunidade") return <TrendingUp className="w-3.5 h-3.5" />;
  return <Bell className="w-3.5 h-3.5" />;
};

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const { data: dashboard, isLoading, isError, error, refetch } = useGetDashboard({
    query: {
      queryKey: ["dashboard"] as const,
      retry: 2,
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10_000),
    },
  });

  const today = new Date().toISOString().slice(0, 10);
  const [selectedDate, setSelectedDate] = useState(today);

  // Admin check — reuses the stats endpoint already available; gracefully fails for non-admins
  const { data: adminStats } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: async () => {
      const res = await apiFetch(`${BASE}/api/licitacoes/admin/stats`, { credentials: "include" });
      if (!res.ok) return { is_admin: false };
      return res.json() as Promise<{ is_admin: boolean }>;
    },
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
  const isAdmin = adminStats?.is_admin ?? false;

  const { data: agendaData } = useQuery({
    queryKey: ["agenda"],
    queryFn: async () => {
      const res = await apiFetch(`${BASE}/api/agenda`, { credentials: "include" });
      if (!res.ok) throw new Error("Erro ao buscar agenda");
      return res.json() as Promise<{
        eventos: Array<{
          id: string; tipo: string; titulo: string; data: string;
          urgencia: string; status: string; link: string; descricao?: string;
        }>;
        resumo: { total: number; criticos: number; atencao: number; proximos7dias: number };
      }>;
    },
  });

  const allEvents = agendaData?.eventos ?? [];

  const eventosDodia = useMemo(
    () => allEvents.filter(e => e.data.slice(0, 10) === selectedDate),
    [allEvents, selectedDate],
  );

  if (isLoading) {
    return (
      <div className="p-8 space-y-6">
        <div className="h-8 w-48 bg-muted animate-pulse rounded" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-32 bg-muted animate-pulse rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-8">
        <PageErrorState error={error} onRetry={() => refetch()} />
      </div>
    );
  }

  if (!dashboard) return null;

  const ufData = (dashboard as any).licitacoesPorUf as Array<{
    uf: string; total: number; percentual: number; monitorado: boolean;
  }> | undefined;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Visão Geral</h1>
        <p className="text-muted-foreground mt-1">Resumo das suas operações e oportunidades ativas.</p>
      </div>

      {/* ── KPI Cards ──────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Valor em Pipeline"
          value={formatCurrency(dashboard.valorTotalPipeline || 0)}
          sub={`Em ${dashboard.totalOportunidades} oportunidades`}
          icon={<Briefcase className="w-4 h-4" />}
          color="text-primary"
          bg="bg-primary/10"
        />
        <KpiCard
          label="Alertas Não Lidos"
          value={String(dashboard.totalAlertasNaoLidos || 0)}
          sub="Ações requeridas"
          icon={<AlertCircle className="w-4 h-4" />}
          color="text-amber-600"
          bg="bg-amber-500/10"
        />
        <KpiCard
          label="Monitoramentos Ativos"
          value={String(dashboard.totalMonitoramentos || 0)}
          sub="Varrendo editais 24/7"
          icon={<Target className="w-4 h-4" />}
          color="text-emerald-600"
          bg="bg-emerald-500/10"
        />
        <KpiCard
          label="Favoritos"
          value={String(dashboard.totalFavoritos || 0)}
          sub="Licitações acompanhadas"
          icon={<Star className="w-4 h-4" />}
          color="text-blue-600"
          bg="bg-blue-500/10"
        />
      </div>

      {/* ── Collector (admin only) ─────────────────────────────────────────── */}
      {isAdmin && (
        <section>
          <h2 className="text-base font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            Infraestrutura
          </h2>
          <div className="max-w-sm">
            <CollectorStatusCard isAdmin={isAdmin} />
          </div>
        </section>
      )}

      {/* ── Novidades / Oportunidades ──────────────────────────────────────── */}
      <section>
        <h2 className="text-base font-semibold text-muted-foreground uppercase tracking-wider mb-3">
          Novidades &amp; Oportunidades
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <NovidadeCard
            icon={<Zap className="w-5 h-5 text-emerald-600" />}
            label="Novas hoje"
            value={(dashboard as any).novasOportunidadesHoje ?? 0}
            bg="bg-emerald-500/8"
            border="border-emerald-200/50"
          />
          <NovidadeCard
            icon={<BarChart3 className="w-5 h-5 text-primary" />}
            label="Vigentes"
            value={(dashboard as any).oportunidadesVigentes ?? 0}
            bg="bg-primary/8"
            border="border-primary/20"
          />
          <NovidadeCard
            icon={<Timer className="w-5 h-5 text-red-500" />}
            label="Iminência de encerramento"
            value={(dashboard as any).iminenciaEncerramento ?? 0}
            bg="bg-red-500/8"
            border="border-red-200/50"
          />
          <NovidadeCard
            icon={<Bell className="w-5 h-5 text-amber-500" />}
            label="Novos andamentos hoje"
            value={(dashboard as any).novosAndamentos ?? 0}
            bg="bg-amber-500/8"
            border="border-amber-200/50"
          />
        </div>
      </section>

      {/* ── Status Badges (Certidões / Documentos) ─────────────────────────── */}
      {((dashboard as any).certidoesVencendo > 0 || (dashboard as any).documentosPendentes > 0) && (
        <div className="flex flex-wrap gap-3">
          {(dashboard as any).certidoesVencendo > 0 && (
            <Link href="/certidoes">
              <div className="flex items-center gap-2 px-4 py-2 rounded-full border border-amber-300 bg-amber-50 dark:bg-amber-500/10 dark:border-amber-600/40 text-amber-700 dark:text-amber-400 text-sm font-medium cursor-pointer hover:shadow-sm transition-shadow">
                <ShieldAlert className="w-4 h-4" />
                {(dashboard as any).certidoesVencendo} certidão(ões) vencendo em 30 dias
              </div>
            </Link>
          )}
          {(dashboard as any).documentosPendentes > 0 && (
            <Link href="/documentos">
              <div className="flex items-center gap-2 px-4 py-2 rounded-full border border-red-300 bg-red-50 dark:bg-red-500/10 dark:border-red-600/40 text-red-700 dark:text-red-400 text-sm font-medium cursor-pointer hover:shadow-sm transition-shadow">
                <FileMinus className="w-4 h-4" />
                {(dashboard as any).documentosPendentes} documento(s) pendente(s)
              </div>
            </Link>
          )}
        </div>
      )}

      {/* ── Main grid: Licitações + Alertas ────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Licitações Recentes */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <FileText className="w-5 h-5 text-muted-foreground" />
              Últimas Licitações Encontradas
            </h2>
            <Link href="/licitacoes" className="text-sm font-medium text-primary hover:underline flex items-center">
              Ver todas <ChevronRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="bg-card border border-border rounded-xl overflow-hidden shadow-sm">
            <div className="divide-y divide-border">
              {dashboard.licitacoesRecentes?.map((lic) => {
                // Constrói URL do portal PNCP: "CNPJ14-uasg-seq6/ano" → pncp.gov.br/editais/CNPJ/ano/num
                const pncpUrl = (() => {
                  const m = String((lic as any).numero ?? "").match(/^(\d{14})-\d+-0*(\d+)\/(\d{4})$/);
                  if (!m) return null;
                  return `https://pncp.gov.br/editais/${m[1]}/${m[3]}/${m[2]}`;
                })();
                return (
                <div key={lic.id} className="p-4 hover:bg-muted/50 transition-colors flex flex-col gap-2">
                  <div className="flex justify-between items-start gap-4">
                    {pncpUrl ? (
                      <a href={pncpUrl} target="_blank" rel="noreferrer"
                        className="font-medium text-primary hover:underline line-clamp-1">
                        {(lic as any).orgaoNome || (lic as any).numero}
                      </a>
                    ) : (
                      <span className="font-medium text-foreground line-clamp-1">
                        {(lic as any).orgaoNome || (lic as any).numero}
                      </span>
                    )}
                    <span className="text-xs font-mono bg-muted px-2 py-1 rounded-md text-muted-foreground whitespace-nowrap">
                      {lic.modalidade}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground line-clamp-2">{lic.objeto}</p>
                  <div className="flex items-center gap-4 text-xs mt-2">
                    <span className="flex items-center gap-1 font-mono text-emerald-600 font-medium">
                      {formatCurrency((lic as any).valorEstimado || 0)}
                    </span>
                    <span className="text-muted-foreground flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      Abertura:{" "}
                      {(lic as any).dataAbertura
                        ? new Date((lic as any).dataAbertura).toLocaleDateString("pt-BR")
                        : "-"}
                    </span>
                    <span className="bg-secondary text-secondary-foreground px-2 py-0.5 rounded-sm">
                      {(lic as any).uf}
                    </span>
                  </div>
                </div>
                );
              })}
              {(!dashboard.licitacoesRecentes || dashboard.licitacoesRecentes.length === 0) && (
                <div className="p-8 text-center text-muted-foreground">
                  Nenhuma licitação recente encontrada.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Alertas Recentes */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-muted-foreground" />
              Alertas Recentes
            </h2>
            <Link href="/alertas" className="text-sm font-medium text-primary hover:underline flex items-center">
              Ver inbox <ChevronRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="bg-card border border-border rounded-xl p-4 shadow-sm flex flex-col gap-3">
            {dashboard.alertasRecentes?.map((alerta) => (
              <div
                key={alerta.id}
                className="flex gap-3 p-3 rounded-lg border border-border bg-background hover:border-primary/50 transition-colors"
              >
                <div className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${alerta.lido ? "bg-muted" : "bg-amber-500"}`} />
                <div className="flex-1 min-w-0">
                  <h4 className={`text-sm font-medium ${alerta.lido ? "text-muted-foreground" : "text-foreground"}`}>
                    {alerta.titulo}
                  </h4>
                  <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{alerta.descricao}</p>
                  <span className="text-[10px] text-muted-foreground mt-1.5 block">
                    {alerta.criadoEm ? new Date(alerta.criadoEm).toLocaleDateString("pt-BR") : "-"}
                  </span>
                </div>
              </div>
            ))}
            {(!dashboard.alertasRecentes || dashboard.alertasRecentes.length === 0) && (
              <div className="text-center text-sm text-muted-foreground py-8">
                Nenhum alerta recente.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Calendário + Ranking por UF ────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Mini calendário + Agenda do dia */}
        <div className="lg:col-span-1 space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <CalendarDays className="w-5 h-5 text-muted-foreground" />
            Agenda
          </h2>
          <div id="dashboard-mini-calendar" className="bg-card border border-border rounded-xl p-4 shadow-sm space-y-5">
            <MiniCalendar
              events={allEvents as CalendarEvent[]}
              selected={selectedDate}
              onSelect={setSelectedDate}
            />

            {/* Divider */}
            <div className="border-t border-border pt-3">
              <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide">
                {selectedDate === today ? "Hoje" : new Date(selectedDate + "T12:00:00").toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" })}
              </p>
              {eventosDodia.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4">Nenhum evento neste dia.</p>
              ) : (
                <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                  {eventosDodia.map(ev => (
                    <Link key={ev.id} href={ev.link}>
                      <div className={`flex items-start gap-2 p-2 rounded-lg border text-xs cursor-pointer hover:opacity-90 transition-opacity ${urgencyBadge(ev.urgencia)}`}>
                        <span className="mt-0.5 flex-shrink-0">{tipoIcon(ev.tipo)}</span>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium line-clamp-1">{ev.titulo}</p>
                          {ev.descricao && <p className="opacity-70 mt-0.5 line-clamp-1">{ev.descricao}</p>}
                        </div>
                        <span className="flex-shrink-0 text-[10px] font-semibold uppercase opacity-70">
                          {urgencyLabel(ev.urgencia)}
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Agenda summary chips — clicável */}
          {agendaData?.resumo && agendaData.resumo.total > 0 && (
            <AgendaChips
              resumo={agendaData.resumo}
              eventos={allEvents}
              onSelectDate={setSelectedDate}
            />
          )}
        </div>

        {/* Licitações por UF — Mapa */}
        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <MapPin className="w-5 h-5 text-muted-foreground" />
            Licitações por Estado
          </h2>
          <div className="bg-card border border-border rounded-xl p-5 shadow-sm">
            {!ufData || ufData.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-6">Sem dados de distribuição por UF.</p>
            ) : (
              <>
                <UfPieChart data={ufData} />
                {/* Top 5 tabela compacta */}
                <div className="mt-4 border-t border-border pt-3">
                  <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">Top estados</p>
                  <div className="grid grid-cols-2 gap-x-6 gap-y-1">
                    {ufData.slice(0, 6).map(item => (
                      <div key={item.uf} className="flex items-center justify-between text-xs">
                        <span className="flex items-center gap-1.5">
                          {item.monitorado && <span className="w-1.5 h-1.5 rounded-full bg-primary flex-shrink-0" />}
                          <span className="font-mono font-bold">{item.uf}</span>
                        </span>
                        <span className="font-mono text-muted-foreground">{item.total.toLocaleString("pt-BR")}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────
function KpiCard({
  label, value, sub, icon, color, bg,
}: { label: string; value: string; sub: string; icon: React.ReactNode; color: string; bg: string }) {
  return (
    <div className="bg-card border border-border p-6 rounded-xl shadow-sm flex flex-col justify-between">
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-medium text-muted-foreground">{label}</span>
        <div className={`p-2 ${bg} ${color} rounded-md`}>{icon}</div>
      </div>
      <div>
        <div className={`text-2xl font-bold font-mono tracking-tight ${color}`}>{value}</div>
        <p className="text-xs text-muted-foreground mt-1">{sub}</p>
      </div>
    </div>
  );
}

function NovidadeCard({
  icon, label, value, bg, border,
}: { icon: React.ReactNode; label: string; value: number; bg: string; border: string }) {
  return (
    <div className={`rounded-xl border ${border} ${bg} p-4 flex items-center gap-4`}>
      <div className="p-2 bg-background/60 rounded-lg shadow-sm flex-shrink-0">{icon}</div>
      <div>
        <div className="text-2xl font-bold font-mono">{value}</div>
        <div className="text-xs text-muted-foreground mt-0.5">{label}</div>
      </div>
    </div>
  );
}

// ─── AgendaChips ──────────────────────────────────────────────────────────────
interface AgendaEvento {
  id: string; tipo: string; titulo: string; data: string;
  urgencia: string; status: string; link: string; descricao?: string;
}

function AgendaChips({
  resumo,
  eventos,
  onSelectDate,
}: {
  resumo: { total: number; criticos: number; atencao: number; proximos7dias: number };
  eventos: AgendaEvento[];
  onSelectDate: (iso: string) => void;
}) {
  const [open, setOpen] = useState<"all" | "critico" | "prox7" | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // Fechar ao clicar fora
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(null);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const filteredEvents = useMemo(() => {
    const hoje = new Date();
    if (open === "critico") return eventos.filter(e => e.urgencia === "critico");
    if (open === "prox7") return eventos.filter(e => {
      const d = new Date(e.data);
      const diff = Math.ceil((d.getTime() - hoje.getTime()) / 86400000);
      return diff >= 0 && diff <= 7;
    });
    return [...eventos].sort((a, b) => a.data.localeCompare(b.data));
  }, [open, eventos]);

  const urgencyDot = (u: string) =>
    u === "critico" ? "bg-red-500" : u === "atencao" ? "bg-amber-400" : "bg-emerald-500";

  const handleEventClick = (evento: AgendaEvento) => {
    onSelectDate(evento.data.slice(0, 10));
    setOpen(null);
    // Scroll suave ao calendário
    const cal = document.getElementById("dashboard-mini-calendar");
    if (cal) cal.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const formatData = (iso: string) => {
    const d = new Date(iso + "T12:00:00");
    return d.toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "short", year: "numeric" });
  };

  return (
    <div className="relative" ref={panelRef}>
      {/* Chips */}
      <div className="flex flex-wrap gap-2 text-xs">
        <button
          onClick={() => setOpen(open === "all" ? null : "all")}
          className={`px-2 py-1 rounded-full transition-colors ${
            open === "all"
              ? "bg-foreground text-background"
              : "bg-muted text-muted-foreground hover:bg-muted/70"
          }`}
        >
          {resumo.total} evento{resumo.total !== 1 ? "s" : ""}
        </button>
        {resumo.criticos > 0 && (
          <button
            onClick={() => setOpen(open === "critico" ? null : "critico")}
            className={`px-2 py-1 rounded-full transition-colors ${
              open === "critico"
                ? "bg-red-500 text-white"
                : "bg-red-500/10 text-red-600 hover:bg-red-500/20"
            }`}
          >
            {resumo.criticos} crítico{resumo.criticos !== 1 ? "s" : ""}
          </button>
        )}
        {resumo.proximos7dias > 0 && (
          <button
            onClick={() => setOpen(open === "prox7" ? null : "prox7")}
            className={`px-2 py-1 rounded-full transition-colors ${
              open === "prox7"
                ? "bg-amber-500 text-white"
                : "bg-amber-500/10 text-amber-600 hover:bg-amber-500/20"
            }`}
          >
            {resumo.proximos7dias} nos próx. 7 dias
          </button>
        )}
      </div>

      {/* Painel de eventos */}
      {open && (
        <div className="absolute bottom-full mb-2 left-0 z-20 w-80 bg-popover border border-border rounded-xl shadow-xl overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-muted/40">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {open === "critico" ? "🔴 Eventos críticos" : open === "prox7" ? "⏰ Próximos 7 dias" : "Todos os eventos"}
            </span>
            <button onClick={() => setOpen(null)} className="p-0.5 rounded hover:bg-muted transition-colors">
              <X className="w-3.5 h-3.5 text-muted-foreground" />
            </button>
          </div>
          <div className="max-h-64 overflow-y-auto divide-y divide-border">
            {filteredEvents.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-6">Nenhum evento nesta categoria.</p>
            ) : (
              filteredEvents.map(ev => (
                <button
                  key={ev.id}
                  onClick={() => handleEventClick(ev)}
                  className="w-full flex items-start gap-2.5 px-3 py-2.5 text-left hover:bg-muted/60 transition-colors group"
                >
                  <span className={`mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${urgencyDot(ev.urgencia)}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium line-clamp-1">{ev.titulo}</p>
                    <p className="text-[11px] text-muted-foreground mt-0.5">{formatData(ev.data)}</p>
                  </div>
                  <CalendarDays className="w-3.5 h-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 mt-0.5" />
                </button>
              ))
            )}
          </div>
          <div className="px-3 py-2 border-t border-border bg-muted/20">
            <Link
              href="/agenda"
              className="text-[11px] font-medium text-primary hover:underline flex items-center gap-1"
              onClick={() => setOpen(null)}
            >
              Ver agenda completa <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
