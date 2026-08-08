import React, { useState, useEffect, useMemo, useRef } from "react";
import { Link, useLocation, useSearch } from "wouter";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Search, MapPin, Building2, Calendar, FileText, Bookmark,
  BookmarkCheck, ChevronLeft, ChevronRight, SlidersHorizontal,
  Download, Printer, RefreshCw, X, Clock, AlertTriangle, CheckCircle,
  XCircle, PauseCircle, Filter, ChevronDown, ChevronUp, ArrowUpDown,
  Zap, Wifi, WifiOff, Database, Loader2, Scale, Hash, Info, Layers,
  ExternalLink, FolderOpen, Eye, EyeOff, Link2, Banknote, Package,
  SquareStack, FileDown, AlertCircle, ClipboardList,
} from "lucide-react";
import { apiFetch } from "@/lib/apiFetch";
import { ToastAction } from "@/components/ui/toast";
import { PageErrorState } from "@/components/PageErrorState";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");
import { fmtLastSync as fmtLastSyncBRT, isValidIsoDate, extract422DateMessage, parseDateInvalidError } from "../lib/dateUtils";
import { useToast } from "../hooks/use-toast";

// ─── Types ────────────────────────────────────────────────────────────────────
interface Licitacao {
  id: string;
  numero: string;
  ano: number;
  modalidade: string;
  modoDisputa?: string | null;
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
  // campos de enriquecimento (via API detalhe / scheduler)
  numeroProcesso?: string | null;
  informacaoComplementar?: string | null;
  amparoLegal?: string | null;
  // campos extras retornados pelo endpoint de detalhe PNCP
  valorTotalHomologado?: number | null;
  numeroParcelas?: number | null;
  tipoContratacao?: string | null;
  categoriaProcesso?: string | null;
  linkSistemaOrigem?: string | null;
  orcamentoSigiloso?: boolean | null;
  unidadeNome?: string | null;
  codigoUnidade?: string | null;
  situacaoCompraNome?: string | null;
}

// Tipo para arquivo de licitação — campos reais retornados pelo PNCP
interface ArquivoLicitacao {
  sequencialDocumento?: number;
  titulo?: string;
  url?: string;
  uri?: string;
  tipoDocumentoDescricao?: string;
  tipoDocumentoNome?: string;
  dataPublicacaoPncp?: string;
  statusAtivo?: boolean;
  cnpj?: string;
  anoCompra?: number;
  sequencialCompra?: number;
}

interface ApiResponse {
  data: Licitacao[];
  total: number;
  page: number;
  totalPages: number;
  source?: "pncp" | "dadosabertos" | "mock" | "banco";
  queued?: boolean;
}


const SORT_OPTIONS = [
  { value: "data_desc",  label: "Mais recentes"         },
  { value: "data_asc",   label: "Mais antigos"           },
  { value: "valor_desc", label: "Maior valor"            },
  { value: "valor_asc",  label: "Menor valor"            },
  { value: "enc_asc",    label: "Encerramento próximo"   },
  { value: "uf_asc",     label: "Estado (A-Z)"           },
  { value: "modal_asc",  label: "Modalidade (A-Z)"       },
  { value: "orgao_asc",  label: "Órgão (A-Z)"            },
];

// ─── Filters ──────────────────────────────────────────────────────────────────
const UFS = [
  "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
  "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO",
];
const MODALIDADES = [
  "Pregão Eletrônico","Pregão Presencial","Concorrência","Tomada de Preços",
  "Convite","Leilão","Dispensa de Licitação","Inexigibilidade",
  "Credenciamento","Manifestação de Interesse",
];
const SITUACOES = [
  { value: "aberta",       label: "Aberta / Publicada" },
  { value: "em_andamento", label: "Em Andamento"       },
  { value: "encerrada",    label: "Encerrada"           },
  { value: "suspensa",     label: "Suspensa"            },
  { value: "cancelada",    label: "Cancelada"           },
];

interface Filters {
  q: string; uf: string; modalidade: string; status: string; esfera: string;
  valorMin: string; valorMax: string; dataInicio: string; dataFim: string;
  somenteVigentes: boolean;
}
const EMPTY: Filters = {
  q: "", uf: "", modalidade: "", status: "", esfera: "",
  valorMin: "", valorMax: "", dataInicio: "", dataFim: "",
  somenteVigentes: false,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────
function formatCurrency(v?: number | null) {
  if (v == null) return null;
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
}
function formatDate(s?: string | null) {
  if (!s) return null;
  try { return new Date(s).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" }); }
  catch { return s; }
}
function daysUntil(s?: string | null): number | null {
  if (!s) return null;
  try { return Math.ceil((new Date(s).getTime() - Date.now()) / 86400000); }
  catch { return null; }
}

function SituacaoBadge({ situacao }: { situacao: string }) {
  const cfg: Record<string, { label: string; cls: string; icon: React.ReactNode }> = {
    aberta:       { label: "Aberta",       cls: "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20", icon: <CheckCircle className="w-3 h-3" /> },
    em_andamento: { label: "Em Andamento", cls: "bg-blue-500/10 text-blue-600 border border-blue-500/20",         icon: <Clock className="w-3 h-3" /> },
    encerrada:    { label: "Encerrada",    cls: "bg-muted text-muted-foreground border border-border",             icon: <XCircle className="w-3 h-3" /> },
    suspensa:     { label: "Suspensa",     cls: "bg-amber-500/10 text-amber-600 border border-amber-500/20",       icon: <PauseCircle className="w-3 h-3" /> },
    cancelada:    { label: "Cancelada",    cls: "bg-red-500/10 text-red-600 border border-red-500/20",             icon: <XCircle className="w-3 h-3" /> },
  };
  const { label, cls, icon } = cfg[situacao] ?? cfg.aberta;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${cls}`}>
      {icon}{label}
    </span>
  );
}

function UrgencyBadge({ dataEncerramento }: { dataEncerramento?: string | null }) {
  const days = daysUntil(dataEncerramento);
  if (days === null || days < 0) return null;
  if (days <= 2) return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold bg-red-500 text-white"><AlertTriangle className="w-3 h-3" />URGENTE</span>;
  if (days <= 7) return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold bg-amber-500 text-white"><Zap className="w-3 h-3" />{days}d</span>;
  return null;
}

// ─── Sidebar section ──────────────────────────────────────────────────────────
function FilterSection({ title, children, defaultOpen = true }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-border last:border-0">
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between py-3 text-sm font-semibold text-foreground hover:text-primary transition-colors">
        {title}
        <ChevronDown className={`w-4 h-4 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <div className="pb-3 space-y-2">{children}</div>}
    </div>
  );
}
const ic = "w-full px-3 py-2 rounded-lg border border-input bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all placeholder:text-muted-foreground";
const sc = "w-full px-3 py-2 rounded-lg border border-input bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all";

// ─── Chips ────────────────────────────────────────────────────────────────────
function Chip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-medium">
      {label}
      <button onClick={onRemove} className="hover:text-destructive ml-0.5 transition-colors"><X className="w-3 h-3" /></button>
    </span>
  );
}

// ─── Date info ────────────────────────────────────────────────────────────────
function DateInfo({ icon, label, value, highlight, urgent, extra }: {
  icon: React.ReactNode; label: string; value: string;
  highlight?: boolean; urgent?: boolean; extra?: string;
}) {
  return (
    <div className={`flex items-center gap-1.5 text-xs ${urgent ? "text-red-500 font-semibold" : highlight ? "text-foreground" : "text-muted-foreground"}`}>
      <span className={urgent ? "text-red-400" : highlight ? "text-primary" : "text-muted-foreground"}>{icon}</span>
      <span className="font-medium">{label}:</span>
      <span>{value}</span>
      {extra && <span className={`ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold ${urgent ? "bg-red-500/10 text-red-500" : "bg-amber-500/10 text-amber-600"}`}>{extra}</span>}
    </div>
  );
}

// ─── Pagination ───────────────────────────────────────────────────────────────
function PagBtn({ children, onClick, disabled, active }: {
  children: React.ReactNode; onClick?: () => void; disabled?: boolean; active?: boolean;
}) {
  return (
    <button onClick={onClick} disabled={disabled}
      className={`min-w-[32px] h-8 px-2 rounded-lg text-sm font-medium transition-colors
        ${active ? "bg-primary text-primary-foreground" : "border border-border text-muted-foreground hover:bg-muted hover:text-foreground"}
        ${disabled ? "opacity-40 cursor-not-allowed" : ""}`}>
      {children}
    </button>
  );
}
function pageNumbers(current: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages: (number | "…")[] = [1];
  if (current > 3) pages.push("…");
  for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) pages.push(i);
  if (current < total - 2) pages.push("…");
  pages.push(total);
  return pages;
}

// ─── URL pública do edital PNCP ───────────────────────────────────────────────
// Formato: "CNPJ14-uasg-seq6/ano" → "https://pncp.gov.br/editais/CNPJ/ano/num"
function gerarUrlPncp(codigoPncp: string): string | null {
  if (!codigoPncp) return null;
  const regex = /^(\d{14})-\d+-(\d+)\/(\d{4})$/;
  const match = codigoPncp.match(regex);
  if (!match) return null;
  const [, cnpj, numeroBruto, ano] = match;
  const numero = parseInt(numeroBruto, 10).toString();
  return `https://pncp.gov.br/editais/${cnpj}/${ano}/${numero}`;
}

// ─── Pending action retry (after re-login) ────────────────────────────────────
const PENDING_ACTION_KEY = "licitaim_pending_action";
type PendingAction =
  | { type: "fav"; id: string; lic: Licitacao; currently: boolean }
  | { type: "ger"; id: string; lic: Licitacao; currently: boolean };

// ─── Main ─────────────────────────────────────────────────────────────────────
const PAGE_SIZES = [10, 20, 50, 100, 150, 200, 300];

export default function Licitacoes() {
  // ── Active state lives in the URL so filters survive navigation ──────
  const search = useSearch();          // e.g. "?q=TI&uf=SP&page=2"
  const [, navigate] = useLocation();

  const url = useMemo(() => {
    const p = new URLSearchParams(search);
    return {
      q:               p.get("q")          ?? "",
      uf:              p.get("uf")         ?? "",
      modalidade:      p.get("modalidade") ?? "",
      status:          p.get("status")     ?? "",
      esfera:          p.get("esfera")     ?? "",
      valorMin:        p.get("valorMin")   ?? "",
      valorMax:        p.get("valorMax")   ?? "",
      dataInicio:      p.get("dataInicio") ?? "",
      dataFim:         p.get("dataFim")    ?? "",
      somenteVigentes: p.get("sv") === "1",
      page:            Math.max(1, parseInt(p.get("page")  ?? "1",  10)),
      limit:           parseInt(p.get("limit") ?? "20", 10) || 20,
      submitted:       p.get("s") === "1",
      sort:            p.get("sort") ?? "data_desc",
    };
  }, [search]);

  const active: Filters = {
    q: url.q, uf: url.uf, modalidade: url.modalidade, status: url.status,
    esfera: url.esfera, valorMin: url.valorMin, valorMax: url.valorMax,
    dataInicio: url.dataInicio, dataFim: url.dataFim, somenteVigentes: url.somenteVigentes,
  };
  const page  = url.page;
  const limit = url.limit;

  // Draft: pending sidebar values, not yet "applied"
  const [draft, setDraft] = useState<Filters>(active);
  // Sync draft when user hits back/forward (URL changes externally)
  useEffect(() => { setDraft(active); }, [search]); // eslint-disable-line react-hooks/exhaustive-deps

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const qc = useQueryClient();
  const { toast } = useToast();

  // ── Shared auth-error handler for background queries ─────────────────
  // Called when a background query (not a mutation) receives a 401.
  // Shows a persistent toast with an "Entrar" button that preserves the
  // current URL (including all filters) as the post-login redirect target.
  const authErrorShownRef = useRef(false);
  function handleQueryAuth401() {
    if (authErrorShownRef.current) return; // only one toast at a time
    authErrorShownRef.current = true;
    const returnTo = window.location.pathname + window.location.search;
    toast({
      variant: "destructive",
      title: "Sessão expirada",
      description: "Faça login novamente para continuar.",
      duration: Infinity,
      action: (
        <ToastAction
          altText="Entrar"
          onClick={() => navigate(`/entrar?redirect=${encodeURIComponent(returnTo)}`)}
        >
          Entrar
        </ToastAction>
      ),
    });
  }

  // ── Carrega favoritos do servidor ─────────────────────────────────────
  // Map: licitacaoId -> fav DB id (para poder deletar pelo id interno)
  const { data: favData, error: favError } = useQuery<{ data: Array<{ id: number; licitacaoId: string }> }>({
    queryKey: ["favoritos-ids"],
    queryFn: async () => {
      const res = await apiFetch(`${BASE}/api/favoritos`, { credentials: "include" });
      if (res.status === 401) throw new Error("401");
      if (!res.ok) return { data: [] };
      return res.json();
    },
    staleTime: 30_000,
    retry: false,
  });

  // Propagate 401 from the favorites background query to the auth toast.
  useEffect(() => {
    if (favError instanceof Error && favError.message.includes("401")) {
      handleQueryAuth401();
    }
  }, [favError]); // eslint-disable-line react-hooks/exhaustive-deps

  const favMap = useMemo<Map<string, number>>(() => {
    const m = new Map<string, number>();
    for (const f of favData?.data ?? []) m.set(f.licitacaoId, f.id);
    return m;
  }, [favData]);

  // Optimistic local overrides: licitacaoId -> true (added) | false (removed)
  const [favOverrides, setFavOverrides] = useState<Map<string, boolean>>(new Map());

  // Derived: a licitação está favoritada?
  function isFav(id: string) {
    if (favOverrides.has(id)) return favOverrides.get(id)!;
    return favMap.has(id);
  }

  const favMutation = useMutation({
    mutationFn: async ({ id, lic, currently }: { id: string; lic: Licitacao; currently: boolean }) => {
      if (currently) {
        // Remove pelo licitacao_id
        const res = await apiFetch(`${BASE}/api/favoritos/by-licitacao/${encodeURIComponent(id)}`, {
          method: "DELETE", credentials: "include",
        });
        if (res.status === 401) throw new Error("401");
        if (!res.ok && res.status !== 404) throw new Error("Erro ao desfavoritar");
      } else {
        // Adiciona com metadados
        const res = await apiFetch(`${BASE}/api/favoritos`, {
          method: "POST", credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            licitacaoId: id,
            licitacaoObjeto: lic.objeto,
            licitacaoOrgao: lic.orgaoNome,
            licitacaoUf: lic.uf,
            licitacaoModalidade: lic.modalidade,
            licitacaoSituacao: lic.situacao,
            licitacaoValor: lic.valorEstimado != null ? String(lic.valorEstimado) : null,
          }),
        });
        if (res.status === 401) throw new Error("401");
        if (!res.ok && res.status !== 409) throw new Error("Erro ao favoritar");
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["favoritos-ids"] });
    },
    onError: (err: unknown, { id, lic, currently }) => {
      // Reverte override em caso de erro
      setFavOverrides(prev => { const m = new Map(prev); m.delete(id); return m; });
      const msg = err instanceof Error ? err.message : String(err);
      const is401 = msg.includes("401") || msg.toLowerCase().includes("não autorizado") || msg.toLowerCase().includes("unauthorized");
      const returnTo = window.location.pathname + window.location.search;
      toast({
        variant: "destructive",
        title: is401 ? "Sessão expirada" : "Erro ao favoritar",
        description: is401
          ? "Faça login novamente para favoritar licitações."
          : "Não foi possível atualizar os favoritos. Tente novamente.",
        action: is401
          ? <ToastAction altText="Entrar" onClick={() => {
              const action: PendingAction = { type: "fav", id, lic, currently };
              sessionStorage.setItem(PENDING_ACTION_KEY, JSON.stringify(action));
              navigate(`/entrar?redirect=${encodeURIComponent(returnTo)}`);
            }}>Entrar</ToastAction>
          : undefined,
      });
    },
  });

  function toggleFav(id: string, lic: Licitacao) {
    // ⚠️ `currently` deve ser calculado ANTES do setFavOverrides para evitar
    // que o closure da mutation capture o estado pós-override errado.
    const currently = isFav(id);
    const next = !currently;
    setFavOverrides(prev => new Map(prev).set(id, next));
    favMutation.mutate({ id, lic, currently });
  }

  // ── Carrega gerenciamentos do servidor ────────────────────────────────
  const { data: gerData, error: gerError } = useQuery<{ data: Array<{ id: number; licitacaoId: string }> }>({
    queryKey: ["gerenciamento-ids"],
    queryFn: async () => {
      const res = await apiFetch(`${BASE}/api/gerenciamento`, { credentials: "include" });
      if (res.status === 401) throw new Error("401");
      if (!res.ok) return { data: [] };
      const json = await res.json();
      return { data: (json.data ?? []).map((g: { id: number; licitacao_id?: string; licitacaoId?: string }) => ({ id: g.id, licitacaoId: g.licitacaoId ?? g.licitacao_id ?? "" })) };
    },
    staleTime: 30_000,
    retry: false,
  });

  // Propagate 401 from the gerenciamento background query to the auth toast.
  useEffect(() => {
    if (gerError instanceof Error && gerError.message.includes("401")) {
      handleQueryAuth401();
    }
  }, [gerError]); // eslint-disable-line react-hooks/exhaustive-deps

  const gerMap = useMemo<Map<string, number>>(() => {
    const m = new Map<string, number>();
    for (const g of gerData?.data ?? []) if (g.licitacaoId) m.set(g.licitacaoId, g.id);
    return m;
  }, [gerData]);

  const [gerOverrides, setGerOverrides] = useState<Map<string, boolean>>(new Map());
  // Armazena o gerenciamentoId retornado pela API imediatamente após a criação,
  // evitando race condition onde isGer=true mas gerMap ainda não foi atualizado.
  const [pendingGerIds, setPendingGerIds] = useState<Map<string, number>>(new Map());

  function isGer(id: string) {
    if (gerOverrides.has(id)) return gerOverrides.get(id)!;
    return gerMap.has(id);
  }

  function gerenciamentoId(id: string): number | null {
    return pendingGerIds.get(id) ?? gerMap.get(id) ?? null;
  }

  const gerMutation = useMutation({
    mutationFn: async ({ id, lic, currently }: { id: string; lic: Licitacao; currently: boolean }) => {
      if (currently) {
        const res = await apiFetch(`${BASE}/api/gerenciamento/by-licitacao/${encodeURIComponent(id)}`, {
          method: "DELETE", credentials: "include",
        });
        if (res.status === 401) throw new Error("401");
        if (!res.ok && res.status !== 404) throw new Error("Erro ao remover gerenciamento");
        return null;
      } else {
        // Validate date fields client-side before sending — tender data may carry
        // non-standard strings that the backend would reject with a 422.
        const dateChecks: Array<{ value: string | null | undefined; label: string }> = [
          { value: lic.dataEncerramento,   label: "Data de Encerramento" },
          { value: lic.dataAbertura,       label: "Data de Abertura" },
          { value: lic.dataPublicacaoPncp, label: "Data de Publicação" },
        ];
        for (const { value, label } of dateChecks) {
          if (value && !isValidIsoDate(value)) {
            throw new Error(`DATE_INVALID:${label}:${value}`);
          }
        }

        const res = await apiFetch(`${BASE}/api/gerenciamento`, {
          method: "POST", credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            licitacaoId: id,
            licitacaoNumero: lic.numero,
            licitacaoObjeto: lic.objeto,
            licitacaoOrgao: lic.orgaoNome,
            licitacaoCnpj: lic.orgaoCnpj,
            licitacaoUf: lic.uf,
            licitacaoMunicipio: lic.municipio,
            licitacaoModalidade: lic.modalidade,
            licitacaoSituacao: lic.situacao,
            licitacaoValor: lic.valorEstimado != null ? String(lic.valorEstimado) : null,
            licitacaoDataEncerramento: lic.dataEncerramento,
            licitacaoDataAbertura: lic.dataAbertura,
            licitacaoDataPublicacao: lic.dataPublicacaoPncp,
            licitacaoLinkPncp: lic.numero ? `https://pncp.gov.br/app/editais/${lic.orgaoCnpj?.replace(/\D/g, "")}/${new Date().getFullYear()}/${lic.numero?.split("/")[0]}` : null,
          }),
        });
        if (res.status === 401) throw new Error("401");
        if (res.status === 409) {
          // Licitação já gerenciada: resolve o id existente via check endpoint
          const check = await apiFetch(`${BASE}/api/gerenciamento/check/${encodeURIComponent(id)}`, {
            credentials: "include",
          });
          if (check.ok) {
            const ck = await check.json();
            if (ck.gerenciamentoId) return { id: ck.gerenciamentoId as number };
          }
          // check falhou — retorna null e aguarda o refetch da query resolver
          return null;
        }
        if (res.status === 422) {
          let msg = "Dado inválido enviado ao servidor.";
          try {
            const json = await res.json();
            msg = extract422DateMessage(json) ?? msg;
          } catch { /* ignore parse errors */ }
          throw new Error(`422:${msg}`);
        }
        if (!res.ok) throw new Error("Erro ao gerenciar");
        // Retorna o novo gerenciamento (com id) para eliminar race condition
        return res.json() as Promise<{ id: number }>;
      }
    },
    onSuccess: (data, { id, currently }) => {
      // Armazena o ID imediatamente para que o link "Acessar Gerenciamento" funcione
      // antes mesmo do refetch da query gerenciamento-ids completar.
      if (!currently && data && "id" in data) {
        setPendingGerIds(prev => new Map(prev).set(id, data.id));
      }
      if (currently) {
        setPendingGerIds(prev => { const m = new Map(prev); m.delete(id); return m; });
      }
      qc.invalidateQueries({ queryKey: ["gerenciamento-ids"] });
      qc.invalidateQueries({ queryKey: ["gerenciamento"] });
    },
    onError: (err: unknown, { id, lic, currently }) => {
      setGerOverrides(prev => { const m = new Map(prev); m.delete(id); return m; });
      const msg = err instanceof Error ? err.message : String(err);
      const is401 = msg === "401" || msg.toLowerCase().includes("unauthorized");
      const returnTo = window.location.pathname + window.location.search;

      // Client-side date validation failure
      const dateToast = parseDateInvalidError(msg);
      if (dateToast) {
        toast({ variant: "destructive", ...dateToast });
        return;
      }

      // Server-side 422 validation error (e.g. unrecognised date string)
      if (msg.startsWith("422:")) {
        toast({
          variant: "destructive",
          title: "Erro de validação",
          description: msg.slice(4),
        });
        return;
      }

      toast({
        variant: "destructive",
        title: is401 ? "Sessão expirada" : currently ? "Erro ao remover gerenciamento" : "Erro ao gerenciar licitação",
        description: is401
          ? "Faça login novamente para gerenciar licitações."
          : "Não foi possível completar a operação. Tente novamente.",
        action: is401
          ? <ToastAction altText="Entrar" onClick={() => {
              const action: PendingAction = { type: "ger", id, lic, currently };
              sessionStorage.setItem(PENDING_ACTION_KEY, JSON.stringify(action));
              navigate(`/entrar?redirect=${encodeURIComponent(returnTo)}`);
            }}>Entrar</ToastAction>
          : undefined,
      });
    },
  });

  function toggleGer(id: string, lic: Licitacao) {
    const currently = isGer(id);
    setGerOverrides(prev => new Map(prev).set(id, !currently));
    gerMutation.mutate({ id, lic, currently });
  }

  // ── Retry pending action after re-login ───────────────────────────────
  // When a 401 occurs the user is prompted to log in. If they click "Entrar",
  // the pending action is saved to sessionStorage so it can be replayed here
  // automatically once the login redirect brings them back to this page.
  useEffect(() => {
    const raw = sessionStorage.getItem(PENDING_ACTION_KEY);
    if (!raw) return;
    // Clear immediately so a page refresh doesn't re-trigger the action.
    sessionStorage.removeItem(PENDING_ACTION_KEY);
    try {
      const action = JSON.parse(raw) as PendingAction;
      if (action.type === "fav") {
        const next = !action.currently;
        setFavOverrides(prev => new Map(prev).set(action.id, next));
        favMutation.mutate({ id: action.id, lic: action.lic, currently: action.currently });
      } else if (action.type === "ger") {
        setGerOverrides(prev => new Map(prev).set(action.id, !action.currently));
        gerMutation.mutate({ id: action.id, lic: action.lic, currently: action.currently });
      }
    } catch {
      // Malformed sessionStorage entry — ignore silently.
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Stats do cache ────────────────────────────────────────────────────
  const { data: statsData, refetch: refetchStats } = useQuery<{
    total: number;
    last_sync: string | null;
    fonte_predominante: string | null;
    is_admin: boolean;
  }>({
    queryKey: ["licitacoes-cache-stats"],
    queryFn: async () => {
      const res = await apiFetch(`${BASE}/api/licitacoes/admin/stats`, { credentials: "include" });
      if (!res.ok) throw new Error("Erro ao buscar stats");
      return res.json();
    },
    staleTime: 60_000,
    retry: false,
  });

  // ── Status do collector standalone ────────────────────────────────────
  const { data: collectorData } = useQuery<{
    lastRun: string | null;
    processed: number;
    errors: number;
    nextRunIn: number | null;
    isStale: boolean;
    portals: Array<{
      portal: string;
      lastRun: string | null;
      processed: number;
      errors: number;
      nextRunIn: number | null;
      isStale: boolean;
      hoursAgo: number | null;
    }>;
  }>({
    queryKey: ["collector-status"],
    queryFn: async () => {
      const res = await apiFetch(`${BASE}/api/collector/status`, { credentials: "include" });
      if (!res.ok) return { lastRun: null, processed: 0, errors: 0, nextRunIn: null };
      return res.json();
    },
    staleTime: 60_000,
    refetchInterval: 120_000,
    retry: false,
    enabled: statsData?.is_admin === true,
  });

  const [syncStatus, setSyncStatus] = useState<"idle" | "running" | "done" | "error">("idle");
  const [syncElapsed, setSyncElapsed] = useState<number | null>(null);
  const syncStartMs   = useRef<number>(0);
  const pollingRef    = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup polling on unmount
  useEffect(() => () => { if (pollingRef.current) clearInterval(pollingRef.current); }, []);

  function stopPolling() {
    if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
  }

  function startPolling() {
    stopPolling();
    pollingRef.current = setInterval(async () => {
      try {
        const res = await apiFetch(`${BASE}/api/licitacoes/admin/sync/status`, { credentials: "include" });
        if (!res.ok) {
          stopPolling();
          setSyncStatus("error");
          setTimeout(() => setSyncStatus("idle"), 5000);
          return;
        }
        const { in_progress } = (await res.json()) as { in_progress: boolean };
        if (!in_progress) {
          stopPolling();
          setSyncElapsed(Math.round((Date.now() - syncStartMs.current) / 1000));
          setSyncStatus("done");
          refetchStats();
          setTimeout(() => setSyncStatus("idle"), 8000);
        }
      } catch {
        stopPolling();
        setSyncStatus("error");
        setTimeout(() => setSyncStatus("idle"), 5000);
      }
    }, 2000);
  }

  async function handleSync() {
    if (syncStatus === "running") return;
    setSyncStatus("running");
    setSyncElapsed(null);
    syncStartMs.current = Date.now();

    try {
      const res = await apiFetch(`${BASE}/api/licitacoes/admin/sync`, {
        method: "POST", credentials: "include",
      });
      if (!res.ok) {
        if (res.status === 409) {
          // Sync já em andamento — faz polling igualmente
          startPolling();
          return;
        }
        // 403 / 503 / outros → volta para idle silenciosamente
        setSyncStatus("idle");
        return;
      }
      // Sync iniciado com sucesso em background — aguarda via polling
      startPolling();
    } catch {
      setSyncStatus("error");
      setTimeout(() => setSyncStatus("idle"), 5000);
    }
  }

  const fmtLastSync = fmtLastSyncBRT;

  const PORTAL_LABELS: Record<string, string> = {
    pncp: "PNCP",
    comprasnet: "ComprasNet",
    bec_sp: "BEC-SP",
  };

  function fmtPortalName(portal: string): string {
    return PORTAL_LABELS[portal] ?? portal;
  }

  function fmtHoursAgo(hoursAgo: number | null): string {
    if (hoursAgo === null) return "sem dados";
    if (hoursAgo < 1) return "< 1h atrás";
    return `há ${hoursAgo.toFixed(1).replace(".0", "")}h`;
  }

  function fmtFonte(fonte: string | null): string {
    if (!fonte) return "";
    if (fonte === "pncp") return "PNCP";
    if (fonte === "dadosabertos") return "Compras.gov.br";
    return fonte;
  }

  /** Build URL. submitted=true adiciona s=1 que dispara a busca. */
  function toURL(f: Filters, p: number, l: number, submitted = false, sort?: string): string {
    const params = new URLSearchParams();
    if (f.q)               params.set("q",          f.q);
    if (f.uf)              params.set("uf",         f.uf);
    if (f.modalidade)      params.set("modalidade", f.modalidade);
    if (f.status)          params.set("status",     f.status);
    if (f.esfera)          params.set("esfera",     f.esfera);
    if (f.valorMin)        params.set("valorMin",   f.valorMin);
    if (f.valorMax)        params.set("valorMax",   f.valorMax);
    if (f.dataInicio)      params.set("dataInicio", f.dataInicio);
    if (f.dataFim)         params.set("dataFim",    f.dataFim);
    if (f.somenteVigentes) params.set("sv",         "1");
    if (submitted)         params.set("s",          "1");
    if (p > 1)             params.set("page",       String(p));
    if (l !== 20)          params.set("limit",      String(l));
    const s = sort ?? url.sort;
    if (s && s !== "data_desc") params.set("sort", s);
    const qs = params.toString();
    return qs ? `/licitacoes?${qs}` : "/licitacoes";
  }

  function setField<K extends keyof Filters>(k: K, v: Filters[K]) {
    setDraft(prev => ({ ...prev, [k]: v }));
  }
  function applyFilters() { navigate(toURL(draft, 1, limit, true)); }
  function clearFilters()  { setDraft(EMPTY); navigate("/licitacoes"); }
  function setPage(p: number) { navigate(toURL(active, Math.max(1, p), limit, url.submitted)); }
  function setLimit(l: number) { navigate(toURL(active, 1, l, url.submitted)); }
  function setSort(s: string)  { navigate(toURL(active, 1, limit, url.submitted, s)); }

  const hasActive = Object.entries(active).some(([k, v]) =>
    k === "somenteVigentes" ? v === true : v !== "");

  // Backend fallback params
  const backendParams = new URLSearchParams();
  if (active.q)          backendParams.set("q",          active.q);
  if (active.uf)              backendParams.set("uf",              active.uf);
  if (active.modalidade)      backendParams.set("modalidade",      active.modalidade);
  if (active.status)          backendParams.set("status",          active.status);
  if (active.valorMin)        backendParams.set("valorMin",        active.valorMin);
  if (active.valorMax)        backendParams.set("valorMax",        active.valorMax);
  if (active.dataInicio)      backendParams.set("dataInicio",      active.dataInicio);
  if (active.dataFim)         backendParams.set("dataFim",         active.dataFim);
  if (active.somenteVigentes) backendParams.set("somenteVigentes", "true");
  backendParams.set("pagina", String(page));
  backendParams.set("limit",  String(limit));

  // Chave estável que ignora `sort` e `s` — ordenação é client-side e não deve re-fetchar
  const stableQueryKey = (() => {
    const p = new URLSearchParams(search);
    p.delete("sort");
    p.delete("s");
    return p.toString();
  })();

  const { data, isLoading, isFetching, isError, error, refetch } = useQuery<ApiResponse>({
    queryKey: ["licitacoes", stableQueryKey],
    enabled:  url.submitted,
    retry: 2,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10_000),
    queryFn: async () => {
      // Chama exclusivamente o backend — ele serve do banco (cache) ou busca nas
      // APIs externas e faz upsert, retornando source="banco"/"pncp"/"dadosabertos"
      const res = await apiFetch(`${BASE}/api/licitacoes?${backendParams}`, { credentials: "include" });
      if (!res.ok) throw new Error("Erro ao buscar licitações");
      const json = await res.json();
      return {
        data:       json.data       ?? [],
        total:      json.total      ?? 0,
        page:       json.page       ?? page,
        totalPages: json.total_pages ?? json.totalPages ?? 1,
        source:     (json.source ?? "banco") as ApiResponse["source"],
      };
    },
  });

  // Ordenação client-side (aplicada na página atual)
  const items = useMemo(() => {
    const arr = [...(data?.data ?? [])];
    switch (url.sort) {
      case "data_asc":   return arr.sort((a, b) => (a.criadoEm < b.criadoEm ? -1 : 1));
      case "valor_desc": return arr.sort((a, b) => (b.valorEstimado ?? -1) - (a.valorEstimado ?? -1));
      case "valor_asc":  return arr.sort((a, b) => ((a.valorEstimado ?? Infinity) - (b.valorEstimado ?? Infinity)));
      case "enc_asc":    return arr.sort((a, b) => {
        if (!a.dataEncerramento) return 1;
        if (!b.dataEncerramento) return -1;
        return a.dataEncerramento < b.dataEncerramento ? -1 : 1;
      });
      case "uf_asc":     return arr.sort((a, b) => a.uf.localeCompare(b.uf));
      case "modal_asc":  return arr.sort((a, b) => a.modalidade.localeCompare(b.modalidade));
      case "orgao_asc":  return arr.sort((a, b) => a.orgaoNome.localeCompare(b.orgaoNome));
      default:           return arr; // data_desc já vem ordenado do backend/PNCP
    }
  }, [data?.data, url.sort]);

  const total      = data?.total      ?? 0;
  const totalPages = data?.totalPages ?? 1;
  const source     = data?.source;
  const queued     = data?.queued ?? false;

  // ── Utilitários de formatação ─────────────────────────────────────────
  function fmtValor(v?: number | null) {
    if (v == null) return "—";
    return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  }
  function fmtData(s?: string | null) {
    if (!s) return "—";
    const d = new Date(s);
    return isNaN(d.getTime()) ? s : d.toLocaleDateString("pt-BR");
  }

  // ── Exportar CSV ──────────────────────────────────────────────────────
  function handleExportCSV() {
    if (!items.length) return;
    const COLS: { label: string; fn: (l: Licitacao) => string }[] = [
      { label: "Número",            fn: l => l.numero ?? "" },
      { label: "Ano",               fn: l => String(l.ano ?? "") },
      { label: "Modalidade",        fn: l => l.modalidade },
      { label: "Situação",          fn: l => l.situacao },
      { label: "Objeto",            fn: l => l.objeto },
      { label: "Valor Estimado",    fn: l => l.valorEstimado != null ? String(l.valorEstimado) : "" },
      { label: "Órgão",             fn: l => l.orgaoNome },
      { label: "CNPJ",              fn: l => l.orgaoCnpj },
      { label: "UF",                fn: l => l.uf },
      { label: "Município",         fn: l => l.municipio },
      { label: "Esfera",            fn: l => l.esfera },
      { label: "Poder",             fn: l => l.poder },
      { label: "Data Abertura",     fn: l => l.dataAbertura ?? "" },
      { label: "Data Encerramento", fn: l => l.dataEncerramento ?? "" },
      { label: "Publicação PNCP",   fn: l => l.dataPublicacaoPncp ?? "" },
      { label: "SRP",               fn: l => l.srp ? "Sim" : "Não" },
    ];

    const esc = (v: string) => `"${v.replace(/"/g, '""')}"`;
    const header = COLS.map(c => esc(c.label)).join(";");
    const rows   = items.map(l => COLS.map(c => esc(c.fn(l))).join(";"));
    const csv    = [header, ...rows].join("\r\n");

    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = `licitacoes_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // ── Imprimir / gerar PDF ──────────────────────────────────────────────
  function handlePrint() {
    if (!items.length) return;

    const filterDesc = (() => {
      const parts: string[] = [];
      if (url.q)            parts.push(`Busca: "${url.q}"`);
      if (url.uf)           parts.push(`UF: ${url.uf}`);
      if (url.modalidade)   parts.push(`Modalidade: ${url.modalidade}`);
      if (url.status)       parts.push(`Situação: ${SITUACOES.find(s => s.value === url.status)?.label ?? url.status}`);
      if (url.valorMin)     parts.push(`Valor mín.: R$ ${Number(url.valorMin).toLocaleString("pt-BR")}`);
      if (url.valorMax)     parts.push(`Valor máx.: R$ ${Number(url.valorMax).toLocaleString("pt-BR")}`);
      if (url.somenteVigentes) parts.push("Somente Vigentes");
      return parts.length ? parts.join(" · ") : "Todos os resultados";
    })();

    const rows = items.map(l => `
      <tr>
        <td>${l.numero ?? "—"}</td>
        <td>${l.modalidade}</td>
        <td>${l.situacao}</td>
        <td class="objeto">${l.objeto}</td>
        <td class="valor">${fmtValor(l.valorEstimado)}</td>
        <td>${l.orgaoNome}</td>
        <td>${l.municipio}/${l.uf}</td>
        <td>${fmtData(l.dataAbertura)}</td>
        <td>${fmtData(l.dataEncerramento)}</td>
      </tr>`).join("");

    const html = `<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <title>LicitAIM — Licitações</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Arial, sans-serif; font-size: 10px; color: #111; padding: 16px; }
    header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; border-bottom: 2px solid #2563eb; padding-bottom: 8px; }
    header h1 { font-size: 16px; color: #2563eb; font-weight: 700; }
    header .meta { text-align: right; color: #555; font-size: 9px; line-height: 1.5; }
    .filtros { background: #f0f4ff; border: 1px solid #c7d7f8; border-radius: 4px; padding: 6px 10px; margin-bottom: 10px; font-size: 9px; color: #374151; }
    .filtros strong { color: #2563eb; }
    table { width: 100%; border-collapse: collapse; font-size: 9px; }
    thead tr { background: #2563eb; color: #fff; }
    thead th { padding: 5px 6px; text-align: left; white-space: nowrap; }
    tbody tr:nth-child(even) { background: #f8faff; }
    tbody tr:hover { background: #e8f0fe; }
    td { padding: 4px 6px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }
    td.objeto { max-width: 220px; }
    td.valor { white-space: nowrap; font-weight: 600; }
    tfoot td { padding: 6px; color: #6b7280; font-style: italic; font-size: 9px; border-top: 1px solid #d1d5db; }
    footer { margin-top: 12px; text-align: center; font-size: 8px; color: #9ca3af; }
    @media print {
      body { padding: 0; }
      @page { margin: 12mm 10mm; size: A4 landscape; }
      header h1 { color: #2563eb !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
      thead tr { background: #2563eb !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
      tbody tr:nth-child(even) { background: #f8faff !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>LicitAIM — Listagem de Licitações</h1>
      <div style="font-size:9px;color:#6b7280;margin-top:2px;">${items.length} registro(s) exibidos · Página ${page} de ${totalPages} · Total na busca: ${total.toLocaleString("pt-BR")}</div>
    </div>
    <div class="meta">
      Gerado em: ${new Date().toLocaleString("pt-BR")}<br/>
      Fonte: ${source === "banco" ? "Cache local" : source === "pncp" ? "PNCP" : source === "dadosabertos" ? "Dados Abertos" : "—"}
    </div>
  </header>

  <div class="filtros"><strong>Filtros aplicados:</strong> ${filterDesc}</div>

  <table>
    <thead>
      <tr>
        <th>Número</th>
        <th>Modalidade</th>
        <th>Situação</th>
        <th>Objeto</th>
        <th>Valor Estimado</th>
        <th>Órgão</th>
        <th>Local</th>
        <th>Abertura</th>
        <th>Encerramento</th>
      </tr>
    </thead>
    <tbody>${rows}</tbody>
    <tfoot>
      <tr><td colspan="9">* Valores em R$. Dados provenientes do Portal Nacional de Contratações Públicas (PNCP).</td></tr>
    </tfoot>
  </table>

  <footer>LicitAIM · ${new Date().getFullYear()} · licitaim.com.br</footer>
  <script>window.onload = () => { window.print(); }</script>
</body>
</html>`;

    const win = window.open("", "_blank", "width=1100,height=750");
    if (!win) { alert("Permita pop-ups para este site para usar a função de impressão."); return; }
    win.document.write(html);
    win.document.close();
  }

  // ── Auto-retry quando busca enfileirada ───────────────────────────────
  // Quando o backend retorna queued=true, o worker Python está coletando dados.
  // Fazemos polling automático a cada 30s até os dados aparecerem.
  const [retryCountdown, setRetryCountdown] = useState<number | null>(null);
  const retryRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // Limpa timer anterior sempre que os dados mudarem
    if (retryRef.current) {
      clearInterval(retryRef.current);
      retryRef.current = null;
      setRetryCountdown(null);
    }
    if (!queued || !url.submitted) return;

    // Inicia contagem regressiva de 30s → refetch
    let secs = 30;
    setRetryCountdown(secs);
    retryRef.current = setInterval(() => {
      secs -= 1;
      if (secs <= 0) {
        clearInterval(retryRef.current!);
        retryRef.current = null;
        setRetryCountdown(null);
        refetch();
      } else {
        setRetryCountdown(secs);
      }
    }, 1000);
    return () => {
      if (retryRef.current) { clearInterval(retryRef.current); retryRef.current = null; }
    };
  }, [queued, url.submitted, data]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") applyFilters();
  };

  return (
    <div className="flex h-full min-h-0">

      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside className={`flex-shrink-0 border-r border-border bg-card overflow-y-auto transition-all duration-300 ${sidebarOpen ? "w-72" : "w-0 overflow-hidden"}`}>
        <div className="p-4 w-72">
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm font-bold text-foreground flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4 text-primary" /> Filtros
            </span>
            {hasActive && (
              <button onClick={clearFilters} className="text-xs text-muted-foreground hover:text-destructive flex items-center gap-1 transition-colors">
                <X className="w-3 h-3" /> Limpar
              </button>
            )}
          </div>

          <div onKeyDown={handleKeyDown}>
            <FilterSection title="Palavra-chave">
              <div className="relative">
                <Search className="absolute left-3 top-2.5 w-4 h-4 text-muted-foreground" />
                <input type="text" placeholder="Objeto, órgão, nº edital..."
                  className={`${ic} pl-9`} value={draft.q}
                  onChange={e => setField("q", e.target.value)} />
              </div>
              <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer select-none pt-1">
                <input type="checkbox" checked={draft.somenteVigentes}
                  onChange={e => setField("somenteVigentes", e.target.checked)}
                  className="rounded border-input" />
                Somente Vigentes (abertas)
              </label>
            </FilterSection>

            <FilterSection title="Estado (UF)">
              <select value={draft.uf} onChange={e => setField("uf", e.target.value)} className={sc}>
                <option value="">Todos os Estados</option>
                {UFS.map(uf => <option key={uf} value={uf}>{uf}</option>)}
              </select>
            </FilterSection>

            <FilterSection title="Modalidade">
              <select value={draft.modalidade} onChange={e => setField("modalidade", e.target.value)} className={sc}>
                <option value="">Todas as Modalidades</option>
                {MODALIDADES.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </FilterSection>

            <FilterSection title="Situação">
              <select value={draft.status} onChange={e => setField("status", e.target.value)} className={sc}>
                <option value="">Todas as Situações</option>
                {SITUACOES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </FilterSection>

            <FilterSection title="Valor Estimado" defaultOpen={false}>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Mínimo (R$)</label>
                  <input type="number" placeholder="0" value={draft.valorMin}
                    onChange={e => setField("valorMin", e.target.value)} className={ic} />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Máximo (R$)</label>
                  <input type="number" placeholder="Sem limite" value={draft.valorMax}
                    onChange={e => setField("valorMax", e.target.value)} className={ic} />
                </div>
              </div>
            </FilterSection>

            <FilterSection title="Data de Publicação" defaultOpen={false}>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">De</label>
                  <input type="date" value={draft.dataInicio} onChange={e => setField("dataInicio", e.target.value)} className={ic} />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Até</label>
                  <input type="date" value={draft.dataFim} onChange={e => setField("dataFim", e.target.value)} className={ic} />
                </div>
              </div>
            </FilterSection>
          </div>

          <div className="mt-4 space-y-2">
            <button onClick={applyFilters}
              className="w-full py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors flex items-center justify-center gap-2">
              <Search className="w-4 h-4" /> Pesquisar
            </button>
            <button onClick={clearFilters}
              className="w-full py-2 rounded-lg border border-border text-sm text-muted-foreground hover:bg-muted transition-colors">
              Limpar filtros
            </button>
          </div>
        </div>
      </aside>

      {/* ── Results area ─────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">

        {/* Toolbar */}
        <div className="border-b border-border bg-card px-6 py-3 flex items-center gap-3 flex-shrink-0">
          <button onClick={() => setSidebarOpen(o => !o)}
            className="p-2 rounded-lg border border-border hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
            title={sidebarOpen ? "Ocultar filtros" : "Mostrar filtros"}>
            <Filter className="w-4 h-4" />
          </button>

          <div className="flex-1 flex items-center gap-2">
            {isLoading || isFetching ? (
              <span className="text-sm text-muted-foreground animate-pulse">Buscando licitações…</span>
            ) : (
              <span className="text-sm font-semibold text-foreground">
                Total de <span className="text-primary">{total.toLocaleString("pt-BR")}</span> licitações
                {hasActive && <span className="text-muted-foreground font-normal"> (filtradas)</span>}
              </span>
            )}

            {/* Source badge */}
            {!isLoading && source && (
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                source === "mock"
                  ? "bg-amber-500/10 text-amber-600 border border-amber-500/20"
                  : "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
              }`}>
                {source === "mock"
                  ? <><WifiOff className="w-3 h-3" /> Dados de exemplo</>
                  : source === "dadosabertos"
                    ? <><Wifi className="w-3 h-3" /> Compras.gov.br</>
                    : source === "banco"
                      ? <><Wifi className="w-3 h-3" /> Banco de dados</>
                      : <><Wifi className="w-3 h-3" /> PNCP</>}
              </span>
            )}
          </div>

          {/* Ordenação */}
          {url.submitted && (
            <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <ArrowUpDown className="w-3.5 h-3.5 flex-shrink-0" />
              <select value={url.sort} onChange={e => setSort(e.target.value)}
                className="border border-input bg-background rounded-lg px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50">
                {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          )}

          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>Mostrar</span>
            <select value={limit} onChange={e => setLimit(Number(e.target.value))}
              className="border border-input bg-background rounded-lg px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50">
              {PAGE_SIZES.map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>

          <button onClick={() => refetch()}
            className="p-2 rounded-lg border border-border hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
            title="Atualizar">
            <RefreshCw className={`w-4 h-4 ${isFetching ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={handlePrint}
            disabled={!items.length}
            className="p-2 rounded-lg border border-border hover:bg-muted transition-colors text-muted-foreground hover:text-foreground disabled:opacity-40 disabled:cursor-not-allowed"
            title="Imprimir / Gerar PDF">
            <Printer className="w-4 h-4" />
          </button>
          <button
            onClick={handleExportCSV}
            disabled={!items.length}
            className="p-2 rounded-lg border border-border hover:bg-muted transition-colors text-muted-foreground hover:text-foreground disabled:opacity-40 disabled:cursor-not-allowed"
            title="Exportar CSV">
            <Download className="w-4 h-4" />
          </button>
        </div>

        {/* Active chips */}
        {hasActive && (
          <div className="px-6 py-2 bg-primary/5 border-b border-border flex items-center gap-2 flex-wrap flex-shrink-0">
            <span className="text-xs text-muted-foreground font-medium">Filtros:</span>
            {active.q && <Chip label={`"${active.q}"`} onRemove={() => navigate(toURL({ ...active, q: "" }, 1, limit, url.submitted))} />}
            {active.uf && <Chip label={active.uf} onRemove={() => navigate(toURL({ ...active, uf: "" }, 1, limit, url.submitted))} />}
            {active.modalidade && <Chip label={active.modalidade} onRemove={() => navigate(toURL({ ...active, modalidade: "" }, 1, limit, url.submitted))} />}
            {active.status && <Chip label={SITUACOES.find(s => s.value === active.status)?.label ?? active.status} onRemove={() => navigate(toURL({ ...active, status: "" }, 1, limit, url.submitted))} />}
            {active.valorMin && <Chip label={`≥ R$ ${Number(active.valorMin).toLocaleString("pt-BR")}`} onRemove={() => navigate(toURL({ ...active, valorMin: "" }, 1, limit, url.submitted))} />}
            {active.valorMax && <Chip label={`≤ R$ ${Number(active.valorMax).toLocaleString("pt-BR")}`} onRemove={() => navigate(toURL({ ...active, valorMax: "" }, 1, limit, url.submitted))} />}
            {active.somenteVigentes && <Chip label="Somente Vigentes" onRemove={() => navigate(toURL({ ...active, somenteVigentes: false }, 1, limit, url.submitted))} />}
          </div>
        )}

        {/* Cache status bar */}
        {statsData && (
          <div className="border-b border-border bg-muted/30 px-6 py-2 flex items-center gap-3 flex-wrap flex-shrink-0 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5 font-medium text-foreground">
              <Database className="w-3.5 h-3.5 text-primary flex-shrink-0" />
              {statsData.total.toLocaleString("pt-BR")} licitações em cache
            </span>
            {statsData.fonte_predominante && (
              <>
                <span className="text-border">·</span>
                <span className="flex items-center gap-1">
                  <Wifi className="w-3 h-3" />
                  {fmtFonte(statsData.fonte_predominante)}
                </span>
              </>
            )}
            {collectorData && collectorData.portals && collectorData.portals.length > 0 && (() => {
              const stalePortals = collectorData.portals.filter(p => p.isStale);
              const tooltipLines = collectorData.portals.map(p =>
                `${fmtPortalName(p.portal)}: ${p.isStale ? "⚠ parou " : "✓ atualizado "}${fmtHoursAgo(p.hoursAgo)}`
              ).join("\n");

              if (stalePortals.length === 0) return null;

              const badgeLabel = stalePortals.map(p => `${fmtPortalName(p.portal)} parou ${fmtHoursAgo(p.hoursAgo)}`).join(", ");

              return (
                <>
                  <span className="text-border">·</span>
                  <span
                    title={tooltipLines}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-700 border border-amber-500/20 font-semibold cursor-default"
                  >
                    <AlertTriangle className="w-3 h-3 flex-shrink-0" />
                    {badgeLabel}
                  </span>
                </>
              );
            })()}
            {statsData?.is_admin && (
              <div className="ml-auto">
                <button
                  onClick={handleSync}
                  disabled={syncStatus === "running"}
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-semibold transition-colors
                    ${syncStatus === "done"
                      ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
                      : syncStatus === "error"
                        ? "bg-red-500/10 text-red-600 border border-red-500/20"
                        : "bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20"
                    }
                    ${syncStatus === "running" ? "opacity-70 cursor-not-allowed" : ""}`}
                >
                  <RefreshCw className={`w-3 h-3 ${syncStatus === "running" ? "animate-spin" : ""}`} />
                  {syncStatus === "done"
                    ? `Concluído${syncElapsed !== null ? ` em ${syncElapsed}s` : ""}`
                    : syncStatus === "error"
                      ? "Erro ao sincronizar"
                      : syncStatus === "running"
                        ? "Sincronizando…"
                        : "Sincronizar agora"}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Banner: coleta em andamento (queued=true) */}
        {queued && url.submitted && !isLoading && (
          <div className="border-b border-amber-500/30 bg-amber-500/8 px-6 py-3 flex items-center gap-3 flex-shrink-0 text-sm">
            <Loader2 className="w-4 h-4 text-amber-600 animate-spin flex-shrink-0" />
            <span className="text-amber-700 font-medium flex-1">
              Coletando dados para esta busca — o worker Python está buscando nas fontes oficiais com rotação de headers.
              {retryCountdown !== null && (
                <span className="text-amber-600 font-normal"> Atualizando em <strong>{retryCountdown}s</strong>…</span>
              )}
            </span>
            <button
              onClick={() => { if (retryRef.current) { clearInterval(retryRef.current); retryRef.current = null; setRetryCountdown(null); } refetch(); }}
              className="flex-shrink-0 px-3 py-1 rounded-md bg-amber-500/20 text-amber-700 text-xs font-semibold hover:bg-amber-500/30 transition-colors border border-amber-500/30"
            >
              <RefreshCw className="w-3 h-3 inline mr-1" />
              Atualizar agora
            </button>
          </div>
        )}

        {/* Cards */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
          {!url.submitted ? (
            /* Ainda não pesquisou — tela de boas-vindas */
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <Search className="w-14 h-14 text-muted-foreground opacity-20 mb-4" />
              <h3 className="text-lg font-semibold text-foreground mb-2">Configure e pesquise</h3>
              <p className="text-muted-foreground text-sm max-w-sm">
                Use os filtros no painel lateral e clique em{" "}
                <strong className="text-foreground">Pesquisar</strong> para buscar licitações públicas.
              </p>
            </div>
          ) : isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-44 bg-muted animate-pulse rounded-xl" />
              ))}
            </div>
          ) : isError ? (
            <PageErrorState error={error} onRetry={() => refetch()} />
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <FileText className="w-14 h-14 text-muted-foreground opacity-30 mb-4" />
              <h3 className="text-lg font-semibold text-foreground mb-2">Nenhuma licitação encontrada</h3>
              <p className="text-muted-foreground text-sm max-w-sm">Tente ampliar o intervalo de datas ou ajustar os filtros.</p>
              <button onClick={clearFilters} className="mt-4 px-4 py-2 rounded-lg border border-border text-sm hover:bg-muted transition-colors">
                Limpar filtros
              </button>
            </div>
          ) : (
            items.map((lic, idx) => (
              <LicitacaoCard
                key={lic.id}
                lic={lic}
                index={(page - 1) * limit + idx + 1}
                isFav={isFav(lic.id)}
                onFav={() => toggleFav(lic.id, lic)}
                isGer={isGer(lic.id)}
                gerId={gerenciamentoId(lic.id)}
                onGer={() => toggleGer(lic.id, lic)}
              />
            ))
          )}
        </div>

        {/* Pagination */}
        {!isLoading && totalPages > 1 && (
          <div className="border-t border-border bg-card px-6 py-3 flex items-center justify-between flex-shrink-0">
            <span className="text-sm text-muted-foreground">Página {page} de {totalPages}</span>
            <div className="flex items-center gap-1">
              <PagBtn disabled={page <= 1} onClick={() => setPage(1)}>«</PagBtn>
              <PagBtn disabled={page <= 1} onClick={() => setPage(page - 1)}><ChevronLeft className="w-4 h-4" /></PagBtn>
              {pageNumbers(page, totalPages).map((n, i) =>
                n === "…"
                  ? <span key={`e${i}`} className="px-2 text-muted-foreground">…</span>
                  : <PagBtn key={n} active={n === page} onClick={() => setPage(Number(n))}>{n}</PagBtn>
              )}
              <PagBtn disabled={page >= totalPages} onClick={() => setPage(page + 1)}><ChevronRight className="w-4 h-4" /></PagBtn>
              <PagBtn disabled={page >= totalPages} onClick={() => setPage(totalPages)}>»</PagBtn>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Card ─────────────────────────────────────────────────────────────────────

/** Linha de detalhe usada no painel expandido */
function DetailRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 min-w-0">
      <span className="text-muted-foreground flex-shrink-0 mt-0.5">{icon}</span>
      <div className="min-w-0">
        <div className="text-xs text-muted-foreground mb-0.5">{label}</div>
        <div className="text-sm font-medium text-foreground break-words">{value}</div>
      </div>
    </div>
  );
}

function LicitacaoCard({ lic, index, isFav, onFav, isGer, gerId, onGer }: {
  lic: Licitacao; index: number; isFav: boolean; onFav: () => void;
  isGer: boolean; gerId: number | null; onGer: () => void;
}) {
  const [expanded,      setExpanded]      = useState(false);
  const [arquivosOpen,  setArquivosOpen]  = useState(false);
  const days     = daysUntil(lic.dataEncerramento);
  const isUrgent = days !== null && days >= 0 && days <= 2;

  // If any date field carries an unrecognisable value the Gerenciar button
  // should be disabled before the user even clicks it, surfacing the problem
  // through a tooltip rather than a post-click toast.
  const gerDateError: string | null = !isGer ? (() => {
    const checks: Array<{ value: string | null | undefined; label: string }> = [
      { value: lic.dataEncerramento,   label: "Data de Encerramento" },
      { value: lic.dataAbertura,       label: "Data de Abertura" },
      { value: lic.dataPublicacaoPncp, label: "Data de Publicação" },
    ];
    for (const { value, label } of checks) {
      if (value && !isValidIsoDate(value)) return label;
    }
    return null;
  })() : null;

  // Busca detalhe enriquecido somente quando o painel é aberto
  const { data: detail, isFetching: loadingDetail } = useQuery<Licitacao>({
    queryKey: ["licitacao-detail", lic.id, lic.numero],
    enabled:  expanded,
    staleTime: 10 * 60 * 1000,
    queryFn: async () => {
      const res = await apiFetch(
        `${BASE}/api/licitacoes/${encodeURIComponent(lic.id)}${lic.numero ? `?pncp=${encodeURIComponent(lic.numero)}` : ""}`,
        { credentials: "include" },
      );
      if (!res.ok) throw new Error("Erro ao buscar detalhe");
      return res.json();
    },
  });

  // Busca arquivos somente quando o modal é aberto
  const { data: arquivos, isFetching: loadingArquivos, isError: arquivosError } = useQuery<ArquivoLicitacao[]>({
    queryKey: ["licitacao-arquivos", lic.id, lic.numero],
    enabled:  arquivosOpen,
    staleTime: 10 * 60 * 1000,
    queryFn: async () => {
      if (!lic.numero) return [];
      const res = await apiFetch(
        `${BASE}/api/licitacoes/arquivos?pncp=${encodeURIComponent(lic.numero)}`,
        { credentials: "include" },
      );
      if (!res.ok) throw new Error("Erro ao buscar arquivos");
      return res.json();
    },
  });

  const d       = detail ?? lic;
  const pncpUrl = gerarUrlPncp(lic.numero);

  return (
    <div className={`bg-card border rounded-xl shadow-sm transition-all group
      ${isUrgent ? "border-red-400/60 ring-1 ring-red-400/20" : "border-border hover:border-primary/40 hover:shadow-md"}`}>
      <div className="p-5">
        {/* Row 1: badges + fav */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-bold text-muted-foreground w-6 text-right flex-shrink-0">{index}</span>
            <SituacaoBadge situacao={lic.situacao} />
            <UrgencyBadge dataEncerramento={lic.dataEncerramento} />
            <span className="px-2.5 py-0.5 rounded bg-primary/10 text-primary text-xs font-bold font-mono">{lic.modalidade}</span>
            {lic.srp && <span className="px-2 py-0.5 rounded bg-violet-500/10 text-violet-600 text-xs font-semibold border border-violet-500/20">SRP</span>}
            {lic.numero && <span className="text-xs text-muted-foreground font-mono">{lic.numero}</span>}
          </div>
          <button onClick={e => { e.preventDefault(); onFav(); }}
            className="flex-shrink-0 p-1.5 rounded-lg hover:bg-muted transition-colors"
            title={isFav ? "Remover dos favoritos" : "Favoritar"}>
            {isFav ? <BookmarkCheck className="w-5 h-5 text-primary" /> : <Bookmark className="w-5 h-5 text-muted-foreground" />}
          </button>
        </div>

        {/* Objeto */}
        {pncpUrl ? (
          <a href={pncpUrl} target="_blank" rel="noreferrer" className="block mb-3">
            <h3 className="text-base font-bold text-foreground leading-snug group-hover:text-primary transition-colors line-clamp-3 cursor-pointer">
              {lic.objeto}
            </h3>
          </a>
        ) : (
          <div className="block mb-3">
            <h3 className="text-base font-bold text-foreground leading-snug line-clamp-3">{lic.objeto}</h3>
          </div>
        )}

        {/* Info grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-2 text-sm">
          <div className="flex items-start gap-2 min-w-0">
            <Building2 className="w-4 h-4 text-muted-foreground flex-shrink-0 mt-0.5" />
            <div className="min-w-0">
              <div className="text-xs text-muted-foreground mb-0.5">Órgão</div>
              <div className="font-medium text-foreground truncate" title={lic.orgaoNome}>{lic.orgaoNome}</div>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <MapPin className="w-4 h-4 text-muted-foreground flex-shrink-0 mt-0.5" />
            <div>
              <div className="text-xs text-muted-foreground mb-0.5">Localidade</div>
              <div className="font-medium text-foreground">{lic.municipio} — {lic.uf}</div>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-muted-foreground text-xs font-bold mt-0.5 flex-shrink-0">R$</span>
            <div>
              <div className="text-xs text-muted-foreground mb-0.5">Valor Estimado</div>
              <div className={`font-bold font-mono ${formatCurrency(lic.valorEstimado) ? "text-emerald-600" : "text-muted-foreground text-xs"}`}>
                {formatCurrency(lic.valorEstimado) ?? "Não estimado"}
              </div>
            </div>
          </div>
        </div>

        {/* Footer: datas + ações */}
        <div className="mt-3 pt-3 border-t border-border flex flex-wrap items-center gap-x-6 gap-y-1.5">
          {lic.dataPublicacaoPncp && <DateInfo icon={<Calendar className="w-3.5 h-3.5" />} label="Publicação"   value={formatDate(lic.dataPublicacaoPncp)!} />}
          {lic.dataAbertura       && <DateInfo icon={<Calendar className="w-3.5 h-3.5" />} label="Abertura"     value={formatDate(lic.dataAbertura)!}        highlight />}
          {lic.dataEncerramento   && (
            <DateInfo
              icon={<Clock className="w-3.5 h-3.5" />}
              label="Encerramento"
              value={formatDate(lic.dataEncerramento)!}
              urgent={isUrgent}
              extra={days !== null && days >= 0 ? `${days}d restantes` : undefined}
            />
          )}

          <div className="ml-auto flex items-center gap-2">
            {/* Ver mais */}
            <button
              onClick={() => setExpanded(v => !v)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs font-semibold text-muted-foreground hover:text-foreground hover:border-primary/40 hover:bg-muted/60 transition-colors">
              {loadingDetail
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              Ver mais
            </button>

            {/* Arquivos */}
            {lic.numero && (
              <button
                onClick={() => setArquivosOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs font-semibold text-muted-foreground hover:text-foreground hover:border-primary/40 hover:bg-muted/60 transition-colors">
                <FolderOpen className="w-3.5 h-3.5" />
                Arquivos
              </button>
            )}

            {/* Gerenciar Licitação */}
            {isGer ? (
              gerId ? (
                <Link
                  href={`/gerenciamento/${gerId}`}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 text-xs font-semibold hover:bg-emerald-500/20 transition-colors">
                  <ClipboardList className="w-3.5 h-3.5" />
                  Acessar Gerenciamento
                </Link>
              ) : (
                <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-emerald-500/40 bg-emerald-500/10 text-emerald-700/60 dark:text-emerald-400/60 text-xs font-semibold cursor-wait">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Carregando…
                </span>
              )
            ) : gerDateError ? (
              /* Date field carries an unrecognisable value — show disabled button
                 with a tooltip so ops can see the problem before clicking. */
              <div className="relative group">
                <button
                  disabled
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs font-semibold text-muted-foreground opacity-50 cursor-not-allowed">
                  <ClipboardList className="w-3.5 h-3.5" />
                  Gerenciar
                </button>
                <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 w-max max-w-[220px] px-2.5 py-1.5 rounded-md bg-popover border border-border text-xs text-foreground shadow-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 text-center leading-snug">
                  Formato de data inválido em «{gerDateError}». Não é possível gerenciar esta licitação.
                </div>
              </div>
            ) : (
              <button
                onClick={onGer}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs font-semibold text-muted-foreground hover:text-foreground hover:border-primary/40 hover:bg-muted/60 transition-colors">
                <ClipboardList className="w-3.5 h-3.5" />
                Gerenciar
              </button>
            )}

            {/* Ver Licitação */}
            {pncpUrl ? (
              <a href={pncpUrl} target="_blank" rel="noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors">
                <ExternalLink className="w-3.5 h-3.5" />
                Ver Licitação
              </a>
            ) : (
              <Link href={`/licitacoes/${encodeURIComponent(lic.id)}${lic.numero ? `?pncp=${encodeURIComponent(lic.numero)}` : ""}`}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors">
                <ExternalLink className="w-3.5 h-3.5" />
                Ver Licitação
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* ── Painel expandido ──────────────────────────────────────────────── */}
      {expanded && (
        <div className="border-t border-border/60 bg-muted/30 rounded-b-xl px-5 py-4 animate-in fade-in slide-in-from-top-1 duration-200">
          {loadingDetail ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Carregando dados detalhados…
            </div>
          ) : (
            <div className="space-y-4">
              {/* Grade de campos compactos */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-3">
                {d.situacaoCompraNome && (
                  <DetailRow icon={<Info className="w-4 h-4" />} label="Situação (original)" value={d.situacaoCompraNome} />
                )}
                {d.modoDisputa && (
                  <DetailRow icon={<Layers className="w-4 h-4" />} label="Modo de Disputa" value={d.modoDisputa} />
                )}
                {d.tipoContratacao && (
                  <DetailRow icon={<SquareStack className="w-4 h-4" />} label="Tipo de Contratação" value={d.tipoContratacao} />
                )}
                {d.categoriaProcesso && (
                  <DetailRow icon={<Package className="w-4 h-4" />} label="Categoria" value={d.categoriaProcesso} />
                )}
                {d.numeroProcesso && (
                  <DetailRow icon={<Hash className="w-4 h-4" />} label="Nº do Processo" value={<span className="font-mono text-xs">{d.numeroProcesso}</span>} />
                )}
                {d.numeroParcelas != null && d.numeroParcelas > 0 && (
                  <DetailRow icon={<SquareStack className="w-4 h-4" />} label="Nº de Parcelas" value={String(d.numeroParcelas)} />
                )}
                {d.valorTotalHomologado != null && d.valorTotalHomologado > 0 && (
                  <DetailRow
                    icon={<Banknote className="w-4 h-4" />}
                    label="Valor Homologado"
                    value={<span className="font-mono font-bold text-emerald-600">
                      {new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(d.valorTotalHomologado)}
                    </span>}
                  />
                )}
                {d.amparoLegal && (
                  <DetailRow icon={<Scale className="w-4 h-4" />} label="Amparo Legal" value={d.amparoLegal} />
                )}
                <DetailRow
                  icon={<Info className="w-4 h-4" />}
                  label="Esfera / Poder"
                  value={[d.esfera, d.poder].filter(Boolean).map(v => v.charAt(0).toUpperCase() + v.slice(1)).join(" · ")}
                />
                {d.unidadeNome && (
                  <DetailRow icon={<Building2 className="w-4 h-4" />} label="Unidade" value={d.unidadeNome} />
                )}
                {d.codigoUnidade && (
                  <DetailRow icon={<Hash className="w-4 h-4" />} label="Cód. Unidade" value={<span className="font-mono text-xs">{d.codigoUnidade}</span>} />
                )}
                {d.orcamentoSigiloso != null && (
                  <DetailRow
                    icon={d.orcamentoSigiloso ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    label="Orçamento"
                    value={d.orcamentoSigiloso ? "Sigiloso" : "Público"}
                  />
                )}
                {d.linkSistemaOrigem && (
                  <DetailRow
                    icon={<Link2 className="w-4 h-4" />}
                    label="Sistema de Origem"
                    value={
                      <a href={d.linkSistemaOrigem} target="_blank" rel="noreferrer"
                        className="text-primary hover:underline text-xs break-all">
                        {d.linkSistemaOrigem}
                      </a>
                    }
                  />
                )}
              </div>

              {/* Informação complementar — destaque */}
              {d.informacaoComplementar && (
                <div className="border border-border/60 rounded-lg p-3 bg-background/50">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground mb-2">
                    <FileText className="w-3.5 h-3.5" />
                    Informação Complementar
                  </div>
                  <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">{d.informacaoComplementar}</p>
                </div>
              )}

              {/* Fallback */}
              {!d.modoDisputa && !d.amparoLegal && !d.numeroProcesso && !d.informacaoComplementar
                && !d.tipoContratacao && !d.valorTotalHomologado && !d.situacaoCompraNome && (
                <p className="text-sm text-muted-foreground italic">
                  Dados complementares não disponíveis para esta licitação.
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Modal de Arquivos ─────────────────────────────────────────────── */}
      {arquivosOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
          onClick={e => { if (e.target === e.currentTarget) setArquivosOpen(false); }}>
          <div className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <div className="flex items-center gap-2">
                <FolderOpen className="w-5 h-5 text-primary" />
                <span className="font-semibold text-foreground">Arquivos da Licitação</span>
              </div>
              <button onClick={() => setArquivosOpen(false)}
                className="p-1.5 rounded-lg hover:bg-muted transition-colors text-muted-foreground hover:text-foreground">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto px-5 py-4">
              {loadingArquivos ? (
                <div className="flex items-center justify-center gap-2 py-10 text-muted-foreground">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Carregando arquivos…
                </div>
              ) : arquivosError ? (
                <div className="flex flex-col items-center gap-2 py-10 text-muted-foreground">
                  <AlertCircle className="w-8 h-8 opacity-40" />
                  <p className="text-sm">Não foi possível carregar os arquivos.</p>
                </div>
              ) : !Array.isArray(arquivos) || arquivos.length === 0 ? (
                <div className="flex flex-col items-center gap-2 py-10 text-muted-foreground">
                  <FolderOpen className="w-10 h-10 opacity-20" />
                  <p className="text-sm">Nenhum arquivo disponível para esta licitação.</p>
                </div>
              ) : (
                <ul className="space-y-1">
                  {(Array.isArray(arquivos) ? arquivos : []).map((arq, i) => {
                    const nomeCompleto = arq.titulo || `Arquivo ${arq.sequencialDocumento ?? i + 1}`;
                    // Remove extensão para abreviar, depois recoloca
                    const dotIdx = nomeCompleto.lastIndexOf(".");
                    const ext  = dotIdx !== -1 ? nomeCompleto.slice(dotIdx) : "";
                    const base = dotIdx !== -1 ? nomeCompleto.slice(0, dotIdx) : nomeCompleto;
                    const MAX  = 42;
                    const nomeExibido = base.length > MAX
                      ? base.slice(0, MAX).trimEnd() + "…" + ext
                      : nomeCompleto;
                    const href = arq.url || arq.uri;
                    const data = arq.dataPublicacaoPncp
                      ? new Date(arq.dataPublicacaoPncp).toLocaleDateString("pt-BR")
                      : null;
                    // Ícone por extensão
                    const isPdf = ext.toLowerCase() === ".pdf";
                    return (
                      <li key={arq.sequencialDocumento ?? i}
                        className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-muted/50 transition-colors group">
                        {/* Ícone de tipo */}
                        <div className={`flex-shrink-0 w-8 h-8 rounded-md flex items-center justify-center text-xs font-bold
                          ${isPdf ? "bg-red-100 text-red-600 dark:bg-red-950/40 dark:text-red-400"
                                  : "bg-blue-100 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400"}`}>
                          {ext.replace(".", "").toUpperCase().slice(0, 3) || <FileText className="w-4 h-4" />}
                        </div>
                        {/* Nome + data */}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-foreground leading-tight truncate" title={nomeCompleto}>
                            {nomeExibido}
                          </p>
                          {data && (
                            <p className="text-xs text-muted-foreground mt-0.5">{data}</p>
                          )}
                        </div>
                        {/* Ícone de download */}
                        {href ? (
                          <a href={href} target="_blank" rel="noreferrer" title="Baixar arquivo"
                            className="flex-shrink-0 p-1.5 rounded-lg text-muted-foreground
                              hover:text-primary hover:bg-primary/10 transition-colors
                              opacity-0 group-hover:opacity-100 focus:opacity-100">
                            <FileDown className="w-4 h-4" />
                          </a>
                        ) : (
                          <span className="flex-shrink-0 w-7" />
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* Footer */}
            <div className="px-5 py-3 border-t border-border text-xs text-muted-foreground">
              {arquivos && arquivos.length > 0 ? `${arquivos.length} arquivo(s) encontrado(s)` : ""}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
