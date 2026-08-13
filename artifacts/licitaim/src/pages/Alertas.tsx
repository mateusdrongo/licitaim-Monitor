import React from "react";
import { fmtDateTime } from "../lib/dateUtils";
import { useListAlertas, useMarcarAlertaLido, useMarcarTodosAlertasLidos } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { getListAlertasQueryKey, getGetDashboardQueryKey } from "@workspace/api-client-react";
import { Bell, CheckCheck, Clock, FileText, Target, AlertCircle } from "lucide-react";
import { PageErrorState } from "@/components/PageErrorState";
import { Link } from "wouter";

export default function Alertas() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error, refetch } = useListAlertas({ limit: 50 }, {
    query: {
      queryKey: getListAlertasQueryKey({ limit: 50 }),
      retry: 2,
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10_000),
    },
  });

  /** Constrói URL do portal PNCP a partir do número de controle */
  function pncpUrl(licitacaoId: string | null | undefined): string | null {
    if (!licitacaoId) return null;
    const m = licitacaoId.match(/^(\d{14})-\d+-0*(\d+)\/(\d{4})$/);
    if (!m) return null;
    return `https://pncp.gov.br/editais/${m[1]}/${m[3]}/${m[2]}`;
  }
  const marcarLido = useMarcarAlertaLido();
  const marcarTodos = useMarcarTodosAlertasLidos();

  const handleMarcarLido = (id: number) => {
    marcarLido.mutate({ id }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListAlertasQueryKey() });
        queryClient.invalidateQueries({ queryKey: getGetDashboardQueryKey() });
        queryClient.invalidateQueries({ queryKey: ["alertas", "nao-lidos"] });
      }
    });
  };

  const handleMarcarTodos = () => {
    marcarTodos.mutate(undefined, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListAlertasQueryKey() });
        queryClient.invalidateQueries({ queryKey: getGetDashboardQueryKey() });
        queryClient.invalidateQueries({ queryKey: ["alertas", "nao-lidos"] });
      }
    });
  };

  const getIcon = (tipo: string) => {
    switch(tipo) {
      case 'nova_licitacao': return <FileText className="w-5 h-5 text-blue-500" />;
      case 'prazo_vencendo': return <Clock className="w-5 h-5 text-red-500" />;
      case 'situacao_alterada': return <AlertCircle className="w-5 h-5 text-amber-500" />;
      default: return <Bell className="w-5 h-5 text-primary" />;
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <Bell className="w-8 h-8 text-primary" /> Inbox de Alertas
          </h1>
          <p className="text-muted-foreground mt-1">Notificações dos seus monitoramentos automáticos.</p>
        </div>
        <button 
          onClick={handleMarcarTodos}
          disabled={marcarTodos.isPending || !data?.totalNaoLidos}
          className="text-sm font-medium text-primary hover:bg-primary/10 px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 disabled:opacity-50"
        >
          <CheckCheck className="w-4 h-4" /> Marcar todos como lidos
        </button>
      </div>

      <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-4 space-y-4">
            {[1, 2, 3, 4, 5].map(i => <div key={i} className="h-24 bg-muted animate-pulse rounded" />)}
          </div>
        ) : data?.data && data.data.length > 0 ? (
          <div className="divide-y divide-border">
            {data.data.map(alerta => (
              <div 
                key={alerta.id} 
                className={`p-5 flex gap-4 transition-colors ${alerta.lido ? 'bg-card' : 'bg-primary/5 hover:bg-primary/10'}`}
              >
                <div className="mt-1">
                  {getIcon(alerta.tipo)}
                </div>
                <div className="flex-1 space-y-1">
                  <div className="flex justify-between items-start gap-4">
                    <h4 className={`font-medium ${alerta.lido ? 'text-foreground' : 'text-primary'}`}>
                      {alerta.titulo}
                    </h4>
                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                      {fmtDateTime(alerta.criadoEm)}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground">{alerta.descricao}</p>
                  
                  {alerta.monitoramentoNome && (
                    <div className="flex items-center gap-1.5 mt-2 text-xs font-medium text-muted-foreground bg-muted w-fit px-2 py-0.5 rounded">
                      <Target className="w-3 h-3" /> Regra: {alerta.monitoramentoNome}
                    </div>
                  )}
                  
                  {/* Link para licitação no PNCP (alertas de monitoramento) */}
                  {alerta.licitacaoId && pncpUrl(alerta.licitacaoId) && (
                    <div className="mt-3">
                      <a
                        href={pncpUrl(alerta.licitacaoId)!}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sm font-medium text-primary hover:underline"
                      >
                        Ver no PNCP →
                      </a>
                    </div>
                  )}
                  {/* Link genérico (ex: /certidoes para alertas de prazo_vencendo) */}
                  {alerta.link && !pncpUrl(alerta.licitacaoId) && (
                    <div className="mt-3">
                      <Link
                        href={alerta.link}
                        className="text-sm font-medium text-primary hover:underline"
                      >
                        {alerta.tipo === "prazo_vencendo" ? "Gerenciar certidões →" : "Ver detalhes →"}
                      </Link>
                    </div>
                  )}
                </div>
                {!alerta.lido && (
                  <button 
                    onClick={() => handleMarcarLido(alerta.id)}
                    className="w-8 h-8 rounded-full hover:bg-primary/20 flex items-center justify-center text-primary self-center transition-colors"
                    title="Marcar como lido"
                  >
                    <CheckCheck className="w-4 h-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
        ) : isError ? (
          <PageErrorState error={error} onRetry={() => refetch()} compact />
        ) : (
          <div className="text-center py-16">
            <Bell className="w-12 h-12 text-muted-foreground mx-auto mb-4 opacity-30" />
            <h3 className="text-lg font-medium">Caixa de entrada limpa</h3>
            <p className="text-muted-foreground mt-1">Você não tem novos alertas no momento.</p>
          </div>
        )}
      </div>
    </div>
  );
}
