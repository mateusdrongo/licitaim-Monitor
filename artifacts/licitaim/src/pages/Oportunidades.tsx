import React from "react";
import { useListOportunidades, useUpdateOportunidade } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { getListOportunidadesQueryKey } from "@workspace/api-client-react";
import { Briefcase, Building2, MoreHorizontal, DollarSign } from "lucide-react";
import { Link } from "wouter";

const COLUNAS = [
  { id: 'identificada', label: 'Identificada' },
  { id: 'qualificada', label: 'Qualificada' },
  { id: 'proposta', label: 'Proposta/Aguardando' },
  { id: 'disputa', label: 'Em Disputa' },
  { id: 'ganhou', label: 'Ganhou (Adjudicada)' },
  { id: 'perdeu', label: 'Perdeu' }
];

export default function Oportunidades() {
  const { data, isLoading } = useListOportunidades({ limit: 100 } as any);
  const updateOp = useUpdateOportunidade();
  const queryClient = useQueryClient();

  const handleMove = (id: number, novoEstagio: any) => {
    updateOp.mutate({ id, data: { estagio: novoEstagio } }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListOportunidadesQueryKey() });
      }
    });
  };

  const oportunidadesPorEstagio = COLUNAS.reduce((acc, col) => {
    acc[col.id] = data?.filter((op: any) => op.estagio === col.id) || [];
    return acc;
  }, {} as Record<string, any[]>);

  const formatCurrency = (value: number | null | undefined) => {
    if (value == null) return "R$ 0,00";
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(value);
  };

  return (
    <div className="p-8 h-screen flex flex-col">
      <div className="mb-6 flex-shrink-0">
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
          <Briefcase className="w-8 h-8 text-primary" /> Pipeline Comercial
        </h1>
        <p className="text-muted-foreground mt-1">Acompanhamento e evolução de negócios e licitações.</p>
      </div>

      <div className="flex-1 overflow-x-auto overflow-y-hidden pb-4">
        <div className="flex gap-6 h-full min-w-max items-start">
          {COLUNAS.map(col => {
            const ops = oportunidadesPorEstagio[col.id] || [];
            const valorTotal = ops.reduce((sum, op) => sum + (op.valorEstimado || 0), 0);
            
            return (
              <div key={col.id} className="w-80 h-full flex flex-col bg-muted/40 border border-border rounded-xl">
                <div className="p-4 border-b border-border bg-card/50 rounded-t-xl">
                  <div className="flex justify-between items-center mb-2">
                    <h3 className="font-semibold text-foreground uppercase tracking-wider text-sm">{col.label}</h3>
                    <span className="bg-muted text-muted-foreground text-xs font-bold px-2 py-0.5 rounded-full">
                      {ops.length}
                    </span>
                  </div>
                  <div className="text-xs font-mono font-medium text-emerald-600">
                    {formatCurrency(valorTotal)}
                  </div>
                </div>

                <div className="p-3 flex-1 overflow-y-auto space-y-3">
                  {isLoading ? (
                    <div className="h-24 bg-muted animate-pulse rounded-lg" />
                  ) : ops.map(op => (
                    <div key={op.id} className="bg-card border border-border p-4 rounded-lg shadow-sm group hover:border-primary/50 transition-colors">
                      <div className="flex justify-between items-start mb-2">
                        <Link href={op.licitacaoId ? `/licitacoes/${op.licitacaoId}` : '#'} className="font-medium text-sm leading-tight text-foreground hover:text-primary transition-colors line-clamp-2">
                          {op.titulo}
                        </Link>
                        
                        <div className="relative group/menu">
                          <button className="text-muted-foreground hover:text-foreground p-1">
                            <MoreHorizontal className="w-4 h-4" />
                          </button>
                          <div className="absolute right-0 top-full mt-1 w-40 bg-popover border border-border shadow-md rounded-md py-1 opacity-0 pointer-events-none group-hover/menu:opacity-100 group-hover/menu:pointer-events-auto z-10">
                            <div className="px-2 py-1 text-xs font-semibold text-muted-foreground">Mover para:</div>
                            {COLUNAS.filter(c => c.id !== col.id).map(c => (
                              <button 
                                key={c.id} 
                                onClick={() => handleMove(op.id, c.id)}
                                className="w-full text-left px-3 py-1.5 text-sm hover:bg-muted"
                              >
                                {c.label}
                              </button>
                            ))}
                          </div>
                        </div>
                      </div>

                      <div className="text-xs text-muted-foreground mb-3 line-clamp-1 flex items-center gap-1.5">
                        <Building2 className="w-3 h-3" /> {op.licitacaoObjeto || 'Órgão não especificado'}
                      </div>

                      <div className="flex items-center justify-between border-t border-border pt-3">
                        <div className="font-mono text-sm font-bold text-emerald-600">
                          {formatCurrency(op.valorEstimado)}
                        </div>
                        {op.probabilidade && (
                          <div className="text-xs font-medium bg-primary/10 text-primary px-1.5 py-0.5 rounded">
                            {op.probabilidade}%
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  {!isLoading && ops.length === 0 && (
                    <div className="text-center py-6 text-sm text-muted-foreground/50 font-medium border-2 border-dashed border-border rounded-lg">
                      Vazio
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
