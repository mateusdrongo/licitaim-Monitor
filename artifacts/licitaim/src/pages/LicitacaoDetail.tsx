import React, { useState } from "react";
import { useParams, Link } from "wouter";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, Building2, Calendar, MapPin, FileText, Star, Plus,
  ExternalLink, Info, DollarSign, Package, Clock, CheckCircle,
  XCircle, PauseCircle, AlertTriangle, Bookmark, BookmarkCheck,
  Hash, Layers, Globe, Shield, Copy, Check,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { apiFetch } from "@/lib/apiFetch";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

// ─── Types ────────────────────────────────────────────────────────────────────
interface Licitacao {
  id: string;
  numero: string;
  ano: number;
  modalidade: string;
  modoDisputa?: string;
  situacao: string;
  objeto: string;
  valorEstimado?: number | null;
  orgaoNome: string;
  orgaoCnpj: string;
  uf: string;
  municipio: string;
  esfera: string;
  poder: string;
  dataAbertura?: string | null;
  dataEncerramento?: string | null;
  dataPublicacaoPncp?: string | null;
  criadoEm: string;
  isFavoritada: boolean;
  srp: boolean;
}

interface Item {
  id?: string | number;
  numero?: number;
  descricao?: string;
  quantidade?: number;
  unidade?: string;
  valorUnitario?: number | null;
  valorTotal?: number | null;
}

interface Documento {
  id?: string | number;
  titulo?: string;
  nomeArquivo?: string;
  url?: string;
  dataPublicacao?: string;
  tipo?: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
// Gera URL pública do edital PNCP a partir do numeroControlePNCP
// Formato: "CNPJ14-uasg-seq6/ano" → "https://pncp.gov.br/editais/CNPJ/ano/num"
function buildPncpUrl(numero: string): string {
  if (!numero) return "https://pncp.gov.br";
  const regex = /^(\d{14})-\d+-(\d+)\/(\d{4})$/;
  const match = numero.match(regex);
  if (match) {
    const [, cnpj, numeroBruto, ano] = match;
    const num = parseInt(numeroBruto, 10).toString();
    return `https://pncp.gov.br/editais/${cnpj}/${ano}/${num}`;
  }
  return `https://pncp.gov.br`;
}

function formatCurrency(v?: number | null) {
  if (v == null) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
}

function formatDate(s?: string | null, time = false) {
  if (!s) return "—";
  try {
    if (time) {
      // ISO datetime — converte para BRT (America/Fortaleza, UTC-3)
      return new Date(s).toLocaleString("pt-BR", {
        timeZone: "America/Fortaleza",
        day: "2-digit", month: "2-digit", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      });
    }
    // Data pura (YYYY-MM-DD) — ancora às 12h para evitar drift de fuso
    const anchor = s.includes("T") ? s : s + "T12:00:00";
    return new Date(anchor).toLocaleDateString("pt-BR", {
      timeZone: "America/Fortaleza",
      day: "2-digit", month: "2-digit", year: "numeric",
    });
  } catch { return s; }
}

function daysUntil(s?: string | null): number | null {
  if (!s) return null;
  try { return Math.ceil((new Date(s).getTime() - Date.now()) / 86400000); }
  catch { return null; }
}

function SituacaoBadge({ situacao }: { situacao: string }) {
  const cfg: Record<string, { label: string; cls: string; icon: React.ReactNode }> = {
    aberta:       { label: "Aberta",       cls: "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20", icon: <CheckCircle className="w-4 h-4" /> },
    em_andamento: { label: "Em Andamento", cls: "bg-blue-500/10 text-blue-600 border border-blue-500/20",         icon: <Clock className="w-4 h-4" /> },
    encerrada:    { label: "Encerrada",    cls: "bg-muted text-muted-foreground border border-border",             icon: <XCircle className="w-4 h-4" /> },
    suspensa:     { label: "Suspensa",     cls: "bg-amber-500/10 text-amber-600 border border-amber-500/20",       icon: <PauseCircle className="w-4 h-4" /> },
    cancelada:    { label: "Cancelada",    cls: "bg-red-500/10 text-red-600 border border-red-500/20",             icon: <XCircle className="w-4 h-4" /> },
  };
  const { label, cls, icon } = cfg[situacao] ?? cfg.aberta;
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-semibold ${cls}`}>
      {icon}{label}
    </span>
  );
}

// ─── Copy button ──────────────────────────────────────────────────────────────
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
      className="p-1 rounded hover:bg-muted transition-colors text-muted-foreground"
      title="Copiar"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

// ─── Stat card ────────────────────────────────────────────────────────────────
function StatCard({ label, value, sub, icon, highlight }: {
  label: string; value: React.ReactNode; sub?: string;
  icon: React.ReactNode; highlight?: boolean;
}) {
  return (
    <div className={`rounded-xl border p-4 space-y-1 ${highlight ? "border-primary/30 bg-primary/5" : "border-border bg-card"}`}>
      <div className="flex items-center gap-2 text-xs text-muted-foreground font-medium uppercase tracking-wider">
        <span className={highlight ? "text-primary" : "text-muted-foreground"}>{icon}</span>
        {label}
      </div>
      <div className={`text-xl font-bold font-mono ${highlight ? "text-emerald-600" : "text-foreground"}`}>{value}</div>
      {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

// ─── Detail Row ───────────────────────────────────────────────────────────────
function DetailRow({ label, value, mono }: { label: string; value?: string | null; mono?: boolean }) {
  if (!value) return null;
  return (
    <div className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-4 py-2.5 border-b border-border last:border-0">
      <dt className="text-xs font-semibold text-muted-foreground uppercase tracking-wider sm:w-40 flex-shrink-0 pt-0.5">{label}</dt>
      <dd className={`text-sm text-foreground flex-1 flex items-center gap-1 ${mono ? "font-mono" : ""}`}>
        {value}
        {mono && <CopyButton text={value} />}
      </dd>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function LicitacaoDetail() {
  const { id } = useParams<{ id: string }>();
  const { toast } = useToast();
  const qc = useQueryClient();
  const [favOverride, setFavOverride] = useState<boolean | null>(null); // null = use server value

  // Read numeroControlePNCP from query param (?pncp=...) — needed for real IDs
  const pncpParam = new URLSearchParams(window.location.search).get("pncp") ?? "";
  // The canonical ID to store as favorito is the licitacao_id = id param
  const licitacaoId = id ?? "";

  // Build detail URL with optional pncp param
  function detailUrl(suffix = "") {
    const base = `${BASE}/api/licitacoes/${encodeURIComponent(id ?? "")}${suffix}`;
    return pncpParam ? `${base}?pncp=${encodeURIComponent(pncpParam)}` : base;
  }

  // ── Fetch licitação ──────────────────────────────────────────────────────
  const { data: lic, isLoading, isError } = useQuery<Licitacao>({
    queryKey: ["licitacao", id, pncpParam],
    queryFn: async () => {
      const res = await apiFetch(detailUrl(), { credentials: "include" });
      if (!res.ok) throw new Error(`Erro ${res.status}`);
      return res.json();
    },
    enabled: !!id,
  });

  // ── Fetch status de favorito ─────────────────────────────────────────────
  const { data: favData } = useQuery<{ isFavoritada: boolean }>({
    queryKey: ["favorito-check", licitacaoId],
    queryFn: async () => {
      const res = await apiFetch(`${BASE}/api/favoritos/check/${encodeURIComponent(licitacaoId)}`, {
        credentials: "include",
      });
      if (!res.ok) return { isFavoritada: false };
      return res.json();
    },
    enabled: !!licitacaoId,
  });

  // Derived: usa override otimista se houver, senão valor do servidor
  const favoritado = favOverride !== null ? favOverride : (favData?.isFavoritada ?? false);

  // ── Toggle favorito ──────────────────────────────────────────────────────
  const toggleFavMutation = useMutation({
    mutationFn: async (next: boolean) => {
      if (next) {
        const res = await apiFetch(`${BASE}/api/favoritos`, {
          method: "POST", credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            licitacaoId,
            licitacaoObjeto:    lic?.objeto,
            licitacaoOrgao:     lic?.orgaoNome,
            licitacaoUf:        lic?.uf,
            licitacaoModalidade: lic?.modalidade,
            licitacaoSituacao:  lic?.situacao,
            licitacaoValor:     lic?.valorEstimado != null ? String(lic.valorEstimado) : null,
          }),
        });
        if (!res.ok && res.status !== 409) throw new Error("Erro ao favoritar");
      } else {
        const res = await apiFetch(`${BASE}/api/favoritos/by-licitacao/${encodeURIComponent(licitacaoId)}`, {
          method: "DELETE", credentials: "include",
        });
        if (!res.ok && res.status !== 404) throw new Error("Erro ao desfavoritar");
      }
    },
    onSuccess: (_data, next) => {
      qc.invalidateQueries({ queryKey: ["favorito-check", licitacaoId] });
      qc.invalidateQueries({ queryKey: ["favoritos-ids"] });
      toast({ title: next ? "Adicionado aos favoritos" : "Removido dos favoritos" });
    },
    onError: () => {
      // Reverte override
      setFavOverride(null);
      toast({ title: "Erro ao atualizar favorito", variant: "destructive" });
    },
  });

  function handleToggleFav() {
    const next = !favoritado;
    setFavOverride(next); // optimistic
    toggleFavMutation.mutate(next);
  }

  // ── Fetch itens ──────────────────────────────────────────────────────────
  const { data: itens, isLoading: loadingItens } = useQuery<Item[]>({
    queryKey: ["licitacao-itens", id, pncpParam],
    queryFn: async () => {
      const res = await apiFetch(detailUrl("/itens"), { credentials: "include" });
      if (!res.ok) return [];
      return res.json();
    },
    enabled: !!id,
  });

  // ── Fetch documentos PNCP ────────────────────────────────────────────────
  const { data: documentos, isLoading: loadingDocs } = useQuery<Documento[]>({
    queryKey: ["licitacao-docs", id, pncpParam],
    queryFn: async () => {
      const res = await apiFetch(detailUrl("/documentos-pncp"), { credentials: "include" });
      if (!res.ok) return [];
      return res.json();
    },
    enabled: !!id,
  });

  // ── Add to pipeline ──────────────────────────────────────────────────────
  const addPipeline = useMutation({
    mutationFn: async () => {
      const res = await apiFetch(`${BASE}/api/oportunidades`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          titulo: `${lic?.modalidade} ${lic?.numero} — ${lic?.orgaoNome}`,
          estagio: "identificada",
          licitacao_id: id,
          valor_estimado: lic?.valorEstimado || 0,
          probabilidade: 10,
        }),
      });
      if (!res.ok) throw new Error("Erro ao criar oportunidade");
      return res.json();
    },
    onSuccess: () => toast({ title: "Adicionado ao Pipeline", description: "Oportunidade criada com sucesso." }),
    onError: () => toast({ title: "Erro", description: "Não foi possível criar a oportunidade.", variant: "destructive" }),
  });

  // ─────────────────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="p-8 max-w-7xl mx-auto space-y-6">
        <div className="h-8 w-40 bg-muted animate-pulse rounded" />
        <div className="h-56 bg-muted animate-pulse rounded-xl" />
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map(i => <div key={i} className="h-24 bg-muted animate-pulse rounded-xl" />)}
        </div>
        <div className="h-64 bg-muted animate-pulse rounded-xl" />
      </div>
    );
  }

  if (isError || !lic) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <Link href="/licitacoes" className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground mb-6">
          <ArrowLeft className="w-4 h-4" /> Voltar para busca
        </Link>
        <div className="border border-border rounded-xl p-12 text-center bg-card">
          <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">Licitação não encontrada</h2>
          <p className="text-muted-foreground text-sm">O edital pode ter sido removido ou o ID está incorreto.</p>
          <Link href="/licitacoes" className="mt-6 inline-block px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors">
            Voltar à busca
          </Link>
        </div>
      </div>
    );
  }

  const days = daysUntil(lic.dataEncerramento);
  const isUrgent = days !== null && days >= 0 && days <= 3;

  const pncpUrl = buildPncpUrl(lic.numero);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">

      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm">
        <Link href="/licitacoes" className="inline-flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors font-medium">
          <ArrowLeft className="w-4 h-4" /> Buscar Licitações
        </Link>
        <span className="text-muted-foreground">/</span>
        <span className="text-foreground font-medium truncate max-w-[300px]">{lic.numero || id}</span>
      </div>

      {/* ── Hero ──────────────────────────────────────────────────────────── */}
      <div className="bg-card border border-border rounded-xl p-6 shadow-sm relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-primary/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3 pointer-events-none" />

        <div className="relative">
          {/* Badges row */}
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <SituacaoBadge situacao={lic.situacao} />

            <span className="px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-bold font-mono">
              {lic.modalidade}
            </span>

            {lic.srp && (
              <span className="px-2.5 py-1 rounded-full bg-violet-500/10 text-violet-600 text-xs font-semibold border border-violet-500/20">
                SRP — Registro de Preços
              </span>
            )}

            {isUrgent && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-red-500 text-white text-xs font-bold">
                <AlertTriangle className="w-3 h-3" />
                {days === 0 ? "ENCERRA HOJE" : `ENCERRA EM ${days}d`}
              </span>
            )}
          </div>

          {/* Objeto */}
          <h1 className="text-2xl lg:text-3xl font-bold leading-tight text-foreground mb-5">
            {lic.objeto}
          </h1>

          {/* Meta row */}
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground mb-6">
            <span className="flex items-center gap-2">
              <Building2 className="w-4 h-4 flex-shrink-0" />
              <span className="font-semibold text-foreground">{lic.orgaoNome}</span>
            </span>
            <span className="flex items-center gap-2">
              <MapPin className="w-4 h-4 flex-shrink-0" />
              {lic.municipio} — {lic.uf}
            </span>
            <span className="flex items-center gap-2">
              <Globe className="w-4 h-4 flex-shrink-0" />
              Esfera <span className="capitalize font-medium text-foreground">{lic.esfera}</span>
            </span>
            {lic.modoDisputa && (
              <span className="flex items-center gap-2">
                <Layers className="w-4 h-4 flex-shrink-0" />
                {lic.modoDisputa}
              </span>
            )}
          </div>

          {/* Actions */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleToggleFav}
              disabled={toggleFavMutation.isPending}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-colors disabled:opacity-60 ${
                favoritado
                  ? "bg-amber-500/10 text-amber-600 border-amber-500/30 hover:bg-amber-500/20"
                  : "border-border text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              {favoritado ? <BookmarkCheck className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
              {favoritado ? "Favoritado" : "Favoritar"}
            </button>

            <button
              onClick={() => addPipeline.mutate()}
              disabled={addPipeline.isPending || addPipeline.isSuccess}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-60"
            >
              <Plus className="w-4 h-4" />
              {addPipeline.isSuccess ? "No Pipeline ✓" : "Adicionar ao Pipeline"}
            </button>

            <a
              href={pncpUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
            >
              <ExternalLink className="w-4 h-4" /> Abrir no PNCP
            </a>
          </div>
        </div>
      </div>

      {/* ── Stat cards ────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Valor Estimado"
          value={lic.valorEstimado ? formatCurrency(lic.valorEstimado) : "Não estimado"}
          icon={<DollarSign className="w-4 h-4" />}
          highlight={!!lic.valorEstimado}
        />
        <StatCard
          label="Abertura"
          value={formatDate(lic.dataAbertura, true)}
          icon={<Calendar className="w-4 h-4" />}
        />
        <StatCard
          label="Encerramento"
          value={formatDate(lic.dataEncerramento, true)}
          sub={days !== null && days >= 0 ? `${days} dia${days !== 1 ? "s" : ""} restante${days !== 1 ? "s" : ""}` : undefined}
          icon={<Clock className="w-4 h-4" />}
          highlight={isUrgent}
        />
        <StatCard
          label="Publicação PNCP"
          value={formatDate(lic.dataPublicacaoPncp)}
          icon={<FileText className="w-4 h-4" />}
        />
      </div>

      {/* ── Body ──────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left col */}
        <div className="lg:col-span-2 space-y-6">

          {/* Itens */}
          <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-border flex items-center gap-2">
              <Package className="w-5 h-5 text-primary" />
              <h2 className="text-base font-semibold">Itens do Edital</h2>
            </div>

            {loadingItens ? (
              <div className="p-6 space-y-2">
                {[1, 2, 3].map(i => <div key={i} className="h-10 bg-muted animate-pulse rounded" />)}
              </div>
            ) : itens && itens.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50 text-muted-foreground font-medium text-xs uppercase tracking-wider">
                    <tr>
                      <th className="px-4 py-3 text-left">Nº</th>
                      <th className="px-4 py-3 text-left">Descrição</th>
                      <th className="px-4 py-3 text-right">Qtd</th>
                      <th className="px-4 py-3 text-right">Valor Unit.</th>
                      <th className="px-4 py-3 text-right">Valor Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {itens.map((item, idx) => (
                      <tr key={item.id ?? idx} className="hover:bg-muted/30 transition-colors">
                        <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{item.numero ?? idx + 1}</td>
                        <td className="px-4 py-3 max-w-xs">
                          <span className="line-clamp-2" title={item.descricao}>{item.descricao || "—"}</span>
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-xs">
                          {item.quantidade ?? "—"} <span className="text-muted-foreground">{item.unidade}</span>
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-xs">{formatCurrency(item.valorUnitario)}</td>
                        <td className="px-4 py-3 text-right font-mono text-xs font-semibold">{formatCurrency(item.valorTotal)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="px-6 py-10 text-center text-muted-foreground text-sm">
                <Package className="w-8 h-8 mx-auto mb-3 opacity-30" />
                Itens não disponíveis para esta licitação.
                <p className="text-xs mt-1">Consulte o edital completo no PNCP para mais detalhes.</p>
              </div>
            )}
          </div>

          {/* Documentos */}
          <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-border flex items-center gap-2">
              <FileText className="w-5 h-5 text-primary" />
              <h2 className="text-base font-semibold">Documentos do Edital</h2>
            </div>

            {loadingDocs ? (
              <div className="p-6 space-y-2">
                {[1, 2].map(i => <div key={i} className="h-12 bg-muted animate-pulse rounded" />)}
              </div>
            ) : documentos && documentos.length > 0 ? (
              <div className="divide-y divide-border">
                {documentos.map((doc, idx) => (
                  <a
                    key={doc.id ?? idx}
                    href={doc.url ?? "#"}
                    target="_blank"
                    rel="noreferrer"
                    className={`flex items-center justify-between px-6 py-3.5 hover:bg-muted/50 transition-colors group ${!doc.url ? "pointer-events-none opacity-50" : ""}`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0 group-hover:text-primary transition-colors" />
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-foreground truncate">{doc.titulo || doc.nomeArquivo || `Documento ${idx + 1}`}</div>
                        {doc.dataPublicacao && <div className="text-xs text-muted-foreground">{formatDate(doc.dataPublicacao)}</div>}
                      </div>
                    </div>
                    <ExternalLink className="w-4 h-4 text-muted-foreground flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </a>
                ))}
              </div>
            ) : (
              <div className="px-6 py-10 text-center text-muted-foreground text-sm">
                <FileText className="w-8 h-8 mx-auto mb-3 opacity-30" />
                Nenhum documento disponível via PNCP.
                <p className="text-xs mt-1">
                  <a href={pncpUrl} target="_blank" rel="noreferrer" className="text-primary underline">
                    Consulte diretamente no portal
                  </a>
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Right col */}
        <div className="space-y-6">

          {/* Identificação */}
          <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-border flex items-center gap-2">
              <Hash className="w-4 h-4 text-primary" />
              <h2 className="text-base font-semibold">Identificação</h2>
            </div>
            <dl className="px-6 py-2">
              <DetailRow label="Nº Controle PNCP" value={lic.numero} mono />
              <DetailRow label="Ano" value={String(lic.ano)} />
              <DetailRow label="Modalidade" value={lic.modalidade} />
              <DetailRow label="Modo de Disputa" value={lic.modoDisputa} />
              <DetailRow label="Esfera" value={lic.esfera} />
              <DetailRow label="Poder" value={lic.poder} />
              {lic.srp && <DetailRow label="Tipo" value="Registro de Preços (SRP)" />}
            </dl>
          </div>

          {/* Órgão */}
          <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-border flex items-center gap-2">
              <Building2 className="w-4 h-4 text-primary" />
              <h2 className="text-base font-semibold">Órgão Responsável</h2>
            </div>
            <dl className="px-6 py-2">
              <DetailRow label="Razão Social" value={lic.orgaoNome} />
              <DetailRow label="CNPJ" value={lic.orgaoCnpj} mono />
              <DetailRow label="Município" value={lic.municipio} />
              <DetailRow label="UF" value={lic.uf} />
            </dl>
          </div>

          {/* Links */}
          <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-border flex items-center gap-2">
              <ExternalLink className="w-4 h-4 text-primary" />
              <h2 className="text-base font-semibold">Links Externos</h2>
            </div>
            <div className="p-4 space-y-2">
              <a
                href={pncpUrl}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between p-3 rounded-lg border border-border hover:border-primary/50 hover:bg-muted/50 transition-colors group"
              >
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Shield className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
                  Portal Nacional de Contratações
                </div>
                <ExternalLink className="w-3.5 h-3.5 text-muted-foreground" />
              </a>
              <a
                href={`https://www.comprasnet.gov.br/seguro/indexportal.asp`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between p-3 rounded-lg border border-border hover:border-primary/50 hover:bg-muted/50 transition-colors group"
              >
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Globe className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
                  ComprasNet
                </div>
                <ExternalLink className="w-3.5 h-3.5 text-muted-foreground" />
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
