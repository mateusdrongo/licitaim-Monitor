import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Clock,
  Database,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { apiFetch } from "@/lib/apiFetch";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

// ─── Types ────────────────────────────────────────────────────────────────────
interface CollectorPortal {
  portal: string;
  last_run: string | null;
  processed: number;
  errors: number;
  next_run_in: number | null;
}

interface AlertState {
  is_stale_alerted: boolean;
  alerted_at: string | null;
  recovered_at: string | null;
}

interface CollectorStatus {
  last_run: string | null;
  processed: number;
  errors: number;
  next_run_in: number | null;
  is_stale: boolean;
  is_running: boolean;
  portals: CollectorPortal[];
  alert_state?: AlertState;
}

const PORTAL_LABELS: Record<string, string> = {
  pncp: "PNCP",
  comprasnet: "ComprasNet",
  bec_sp: "BEC/SP",
};

// ─── Helpers ──────────────────────────────────────────────────────────────────
function formatRelativeTime(iso: string | null): string {
  if (!iso) return "nunca";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "agora mesmo";
  if (diff < 3600) return `${Math.floor(diff / 60)} min atrás`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h atrás`;
  return `${Math.floor(diff / 86400)}d atrás`;
}

function formatNextRun(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds === 0) return "iminente";
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

// ─── Component ────────────────────────────────────────────────────────────────
export function CollectorStatusCard({ isAdmin }: { isAdmin: boolean }) {
  const { data, isLoading, isError, refetch, isFetching } = useQuery<CollectorStatus>({
    queryKey: ["collector-status"],
    queryFn: async () => {
      const res = await apiFetch(`${BASE}/api/collector/status`, { credentials: "include" });
      if (!res.ok) throw new Error("Falha ao buscar status do collector");
      return res.json();
    },
    refetchInterval: 30_000,
  });

  const [isTriggering, setIsTriggering] = useState(false);
  const [runMsg, setRunMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const handleRunNow = async () => {
    setIsTriggering(true);
    setRunMsg(null);
    try {
      const res = await apiFetch(`${BASE}/api/collector/run`, {
        method: "POST",
        credentials: "include",
      });
      if (res.status === 409) {
        setRunMsg({ type: "err", text: "Já há um ciclo em andamento." });
      } else if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setRunMsg({ type: "err", text: body?.detail ?? "Erro ao iniciar coleta." });
      } else {
        setRunMsg({ type: "ok", text: "Ciclo iniciado. Aguarde…" });
        // Poll more frequently while running
        setTimeout(() => refetch(), 3_000);
        setTimeout(() => refetch(), 10_000);
        setTimeout(() => refetch(), 30_000);
      }
    } catch {
      setRunMsg({ type: "err", text: "Falha de conexão." });
    } finally {
      setIsTriggering(false);
    }
  };

  const isRunning = data?.is_running ?? false;

  // Determine health colour
  const health: "green" | "yellow" | "red" =
    isError || !data || data.is_stale
      ? "red"
      : data.errors > 0
      ? "yellow"
      : "green";

  const healthConfig = {
    green: {
      dot: "bg-emerald-500",
      label: "Operacional",
      labelClass: "text-emerald-600",
      border: "border-emerald-200/60",
      bg: "bg-emerald-500/8",
      icon: <CheckCircle2 className="w-4 h-4 text-emerald-600" />,
    },
    yellow: {
      dot: "bg-amber-400",
      label: "Com erros",
      labelClass: "text-amber-600",
      border: "border-amber-200/60",
      bg: "bg-amber-500/8",
      icon: <AlertCircle className="w-4 h-4 text-amber-500" />,
    },
    red: {
      dot: "bg-red-500",
      label: data?.last_run == null ? "Nunca executou" : "Inativo",
      labelClass: "text-red-600",
      border: "border-red-200/60",
      bg: "bg-red-500/8",
      icon: <XCircle className="w-4 h-4 text-red-500" />,
    },
  }[health];

  return (
    <div className={`rounded-xl border ${healthConfig.border} ${healthConfig.bg} p-5 space-y-4`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-background/60 rounded-md shadow-sm">
            <Database className="w-4 h-4 text-muted-foreground" />
          </div>
          <span className="text-sm font-semibold">Collector</span>
          {/* Animated pulse dot */}
          <span className="relative flex h-2 w-2">
            {health === "green" && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            )}
            <span className={`relative inline-flex rounded-full h-2 w-2 ${healthConfig.dot}`} />
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium ${healthConfig.labelClass} flex items-center gap-1`}>
            {healthConfig.icon}
            {healthConfig.label}
          </span>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="p-1 rounded hover:bg-background/60 transition-colors text-muted-foreground disabled:opacity-50"
            title="Atualizar"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          <div className="h-4 w-32 bg-muted animate-pulse rounded" />
          <div className="h-4 w-48 bg-muted animate-pulse rounded" />
        </div>
      ) : isError || !data ? (
        <p className="text-xs text-red-500">Não foi possível obter o status do collector.</p>
      ) : (
        <>
          {/* Global stats */}
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="bg-background/60 rounded-lg px-2 py-2">
              <div className="text-base font-bold font-mono text-foreground">
                {data.processed.toLocaleString("pt-BR")}
              </div>
              <div className="text-[10px] text-muted-foreground mt-0.5">processados</div>
            </div>
            <div className="bg-background/60 rounded-lg px-2 py-2">
              <div className={`text-base font-bold font-mono ${data.errors > 0 ? "text-red-500" : "text-foreground"}`}>
                {data.errors}
              </div>
              <div className="text-[10px] text-muted-foreground mt-0.5">erros</div>
            </div>
            <div className="bg-background/60 rounded-lg px-2 py-2">
              <div className="text-base font-bold font-mono text-foreground">
                {formatNextRun(data.next_run_in)}
              </div>
              <div className="text-[10px] text-muted-foreground mt-0.5">próx. ciclo</div>
            </div>
          </div>

          {/* Last run */}
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Clock className="w-3 h-3 flex-shrink-0" />
            <span>
              Último ciclo:{" "}
              <span className="font-medium text-foreground">
                {formatRelativeTime(data.last_run)}
              </span>
              {data.last_run && (
                <span className="ml-1 opacity-60">
                  ({new Date(data.last_run).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })})
                </span>
              )}
            </span>
          </div>

          {/* Alert state */}
          {data.alert_state?.is_stale_alerted && data.alert_state.alerted_at && (
            <div className="flex items-center gap-1.5 text-xs text-amber-600">
              <AlertCircle className="w-3 h-3 flex-shrink-0" />
              <span>
                Alerta enviado em{" "}
                <span className="font-medium">
                  {new Date(data.alert_state.alerted_at).toLocaleString("pt-BR", { timeStyle: "short" })}
                </span>
                <span className="ml-1 opacity-70">
                  ({new Date(data.alert_state.alerted_at).toLocaleDateString("pt-BR", { dateStyle: "short" })})
                </span>
              </span>
            </div>
          )}

          {/* Admin: Run now button */}
          {isAdmin && (
            <div className="border-t border-border/50 pt-3 space-y-2">
              <button
                onClick={handleRunNow}
                disabled={isRunning || isTriggering}
                className="w-full flex items-center justify-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isRunning || isTriggering ? "animate-spin" : ""}`} />
                {isRunning ? "Coletando…" : isTriggering ? "Iniciando…" : "Executar agora"}
              </button>
              {runMsg && (
                <p className={`text-[11px] text-center ${runMsg.type === "ok" ? "text-emerald-600" : "text-red-500"}`}>
                  {runMsg.text}
                </p>
              )}
            </div>
          )}

          {/* Per-portal breakdown */}
          {data.portals.length > 0 && (
            <div className="border-t border-border/50 pt-3 space-y-1.5">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                Por portal
              </p>
              {data.portals.map((p) => {
                const portalHealth = p.errors > 0 ? "yellow" : p.last_run == null ? "red" : "green";
                const dotColor =
                  portalHealth === "green" ? "bg-emerald-500" :
                  portalHealth === "yellow" ? "bg-amber-400" : "bg-red-500";
                return (
                  <div key={p.portal} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotColor}`} />
                      <span className="font-medium">{PORTAL_LABELS[p.portal] ?? p.portal}</span>
                    </div>
                    <div className="flex items-center gap-3 text-muted-foreground font-mono">
                      <span title="Processados">
                        <Activity className="w-3 h-3 inline mr-0.5 opacity-60" />
                        {p.processed.toLocaleString("pt-BR")}
                      </span>
                      {p.errors > 0 && (
                        <span className="text-red-500" title="Erros">
                          ✕ {p.errors}
                        </span>
                      )}
                      <span title="Última execução" className="text-[10px]">
                        {formatRelativeTime(p.last_run)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
