import React from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { Link } from "wouter";
import {
  Star, Building2, MapPin, Calendar, Bookmark, BookmarkCheck,
  Loader2, Trash2, ExternalLink, FileText,
} from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

interface FavoritoLicitacao {
  numero?: string;
  objeto: string;
  orgaoNome: string;
  uf: string;
  modalidade: string;
  situacao: string;
  valorEstimado?: number | null;
}

interface Favorito {
  id: number;
  licitacaoId: string;
  nota?: string | null;
  criadoEm?: string | null;
  licitacao: FavoritoLicitacao;
}

function formatCurrency(value: number | null | undefined) {
  if (value == null) return null;
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value);
}

function formatDate(iso: string | null | undefined) {
  if (!iso) return null;
  try { return new Date(iso).toLocaleDateString("pt-BR"); } catch { return iso; }
}

/** Gera a URL pública de uma licitação no PNCP a partir do número de controle. */
function gerarUrlPncp(numero?: string | null): string | null {
  if (!numero) return null;
  const m = numero.match(/^(\d{14})-\d+-(\d+)\/(\d{4})$/);
  if (!m) return null;
  const [, cnpj, seq, ano] = m;
  const seqFormatado = String(parseInt(seq, 10));
  return `https://pncp.gov.br/app/editais/${cnpj}/${ano}/${seqFormatado}`;
}

export default function Favoritos() {
  const qc = useQueryClient();

  const { data, isLoading } = useQuery<{ data: Favorito[]; total: number }>({
    queryKey: ["favoritos"],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/favoritos`, { credentials: "include" });
      if (!res.ok) return { data: [], total: 0 };
      return res.json();
    },
    staleTime: 30_000,
  });

  const removeMutation = useMutation({
    mutationFn: async (licitacaoId: string) => {
      const res = await fetch(`${BASE}/api/favoritos/by-licitacao/${encodeURIComponent(licitacaoId)}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok && res.status !== 404) throw new Error("Erro ao remover favorito");
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["favoritos"] });
      qc.invalidateQueries({ queryKey: ["favoritos-ids"] });
    },
  });

  const items = data?.data ?? [];

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Cabeçalho */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2.5">
            <Star className="w-7 h-7 text-amber-500 fill-amber-500" />
            Favoritos
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            Licitações que você está acompanhando de perto.
          </p>
        </div>
        {items.length > 0 && (
          <span className="text-sm text-muted-foreground">
            {items.length} licitaç{items.length === 1 ? "ão" : "ões"}
          </span>
        )}
      </div>

      {/* Conteúdo */}
      <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
            <Loader2 className="w-5 h-5 animate-spin" />
            Carregando favoritos…
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-16">
            <Star className="w-12 h-12 text-muted-foreground mx-auto mb-4 opacity-20" />
            <h3 className="text-base font-semibold">Nenhum favorito ainda</h3>
            <p className="text-muted-foreground text-sm mt-1 max-w-xs mx-auto">
              Na lista de licitações, clique no{" "}
              <Bookmark className="inline w-4 h-4 mb-0.5" /> para salvar uma licitação aqui.
            </p>
            <Link href="/licitacoes"
              className="inline-flex items-center gap-1.5 mt-4 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors">
              Ir para Licitações
            </Link>
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {items.map(fav => {
              const pncpUrl = gerarUrlPncp(fav.licitacaoId);
              const valor   = formatCurrency(fav.licitacao.valorEstimado);
              const isRemoving = removeMutation.isPending && removeMutation.variables === fav.licitacaoId;

              return (
                <li key={fav.id}
                  className={`p-5 hover:bg-muted/30 transition-colors flex flex-col md:flex-row gap-4 ${isRemoving ? "opacity-40" : ""}`}>
                  {/* Info principal */}
                  <div className="flex-1 min-w-0 space-y-1.5">
                    {/* Badges */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="px-2 py-0.5 rounded bg-primary/10 text-primary text-xs font-bold font-mono">
                        {fav.licitacao.modalidade}
                      </span>
                      <SituacaoBadge situacao={fav.licitacao.situacao} />
                      {fav.licitacaoId && (
                        <span className="text-xs text-muted-foreground font-mono truncate max-w-[240px]">
                          {fav.licitacaoId}
                        </span>
                      )}
                    </div>

                    {/* Objeto */}
                    <p className="text-sm font-semibold text-foreground line-clamp-2 leading-snug">
                      {fav.licitacao.objeto}
                    </p>

                    {/* Meta */}
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Building2 className="w-3.5 h-3.5" />
                        {fav.licitacao.orgaoNome}
                      </span>
                      <span className="flex items-center gap-1">
                        <MapPin className="w-3.5 h-3.5" />
                        {fav.licitacao.uf}
                      </span>
                      {fav.criadoEm && (
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5" />
                          Salvo em {formatDate(fav.criadoEm)}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Coluna direita */}
                  <div className="flex md:flex-col items-center md:items-end justify-between md:justify-between gap-3 md:min-w-[140px]">
                    {valor ? (
                      <div className="text-right">
                        <div className="text-xs text-muted-foreground mb-0.5">Valor Estimado</div>
                        <div className="font-mono font-bold text-emerald-600 text-sm">{valor}</div>
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground italic">Valor não estimado</span>
                    )}

                    <div className="flex items-center gap-1.5">
                      {pncpUrl && (
                        <a href={pncpUrl} target="_blank" rel="noreferrer"
                          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-border text-xs font-semibold text-muted-foreground hover:text-foreground hover:border-primary/40 hover:bg-muted/60 transition-colors"
                          title="Ver no PNCP">
                          <ExternalLink className="w-3.5 h-3.5" />
                          PNCP
                        </a>
                      )}
                      <button
                        onClick={() => removeMutation.mutate(fav.licitacaoId)}
                        disabled={isRemoving}
                        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-border text-xs font-semibold text-muted-foreground hover:text-red-600 hover:border-red-300 hover:bg-red-50 dark:hover:bg-red-950/20 transition-colors disabled:opacity-50"
                        title="Remover dos favoritos">
                        {isRemoving
                          ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          : <Trash2 className="w-3.5 h-3.5" />}
                        Remover
                      </button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

// ── Componentes auxiliares ────────────────────────────────────────────────────

function SituacaoBadge({ situacao }: { situacao: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    aberta:       { label: "Aberta",       cls: "bg-emerald-100 text-emerald-700 border-emerald-200" },
    em_andamento: { label: "Em Andamento", cls: "bg-blue-100 text-blue-700 border-blue-200" },
    encerrada:    { label: "Encerrada",    cls: "bg-zinc-100 text-zinc-600 border-zinc-200" },
    cancelada:    { label: "Cancelada",    cls: "bg-red-100 text-red-700 border-red-200" },
    suspensa:     { label: "Suspensa",     cls: "bg-amber-100 text-amber-700 border-amber-200" },
  };
  const s = map[situacao] ?? { label: situacao, cls: "bg-muted text-muted-foreground border-border" };
  return (
    <span className={`px-2 py-0.5 rounded border text-xs font-semibold ${s.cls}`}>
      {s.label}
    </span>
  );
}
