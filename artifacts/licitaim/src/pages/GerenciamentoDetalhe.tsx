import React, { useState } from "react";
import { Link, useParams, useLocation } from "wouter";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/apiFetch";
import {
  ArrowLeft, ClipboardList, Building2, MapPin, Calendar, ExternalLink,
  CheckCircle2, Clock, AlertTriangle, XCircle, Trophy, Plus, Trash2,
  Edit3, Save, X, Loader2, StickyNote, CheckSquare, Tag,
  TrendingUp, Flag, ChevronDown, ChevronUp, ShieldCheck, FileCheck,
  BellRing,
} from "lucide-react";
import { fmtDateBRT, fmtDateTime } from "../lib/dateUtils";
import { useToast } from "../hooks/use-toast";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

// ─── URL pública do edital PNCP ───────────────────────────────────────────────
// Formato do código: "CNPJ14-uasg-seq6/ano" → "https://pncp.gov.br/editais/CNPJ/ano/num"
function gerarUrlPncp(codigoPncp?: string | null): string | null {
  if (!codigoPncp) return null;
  const match = codigoPncp.match(/^(\d{14})-\d+-(\d+)\/(\d{4})$/);
  if (!match) return null;
  const [, cnpj, numeroBruto, ano] = match;
  const numero = parseInt(numeroBruto, 10).toString();
  return `https://pncp.gov.br/editais/${cnpj}/${ano}/${numero}`;
}

// ── Types ──────────────────────────────────────────────────────────────────

interface GerItem {
  id: number;
  licitacaoId: string;
  licitacaoNumero?: string;
  licitacaoObjeto?: string;
  licitacaoOrgao?: string;
  licitacaoCnpj?: string;
  licitacaoUf?: string;
  licitacaoMunicipio?: string;
  licitacaoModalidade?: string;
  licitacaoSituacao?: string;
  licitacaoValor?: string;
  licitacaoDataAbertura?: string;
  licitacaoDataEncerramento?: string;
  licitacaoDataPublicacao?: string;
  licitacaoLinkPncp?: string;
  status: string;
  notasGerais?: string;
  responsavel?: string;
  resultado?: string | null;
  valorProposta?: number | null;
  totalTarefas: number;
  tarefasConcluidas: number;
  totalAnotacoes: number;
  criadoEm: string;
  atualizadoEm: string;
}

interface Tarefa {
  id: number;
  gerenciamentoId: number;
  titulo: string;
  descricao?: string;
  prazo?: string;
  concluida: boolean;
  prioridade: string;
  categoria: string;
  concluidaEm?: string;
  criadoEm: string;
}

interface Anotacao {
  id: number;
  gerenciamentoId: number;
  conteudo: string;
  criadoEm: string;
  atualizadoEm: string;
}

interface Habilitacao {
  id: number;
  gerenciamentoId: number;
  documento: string;
  status: string;
  observacoes?: string;
  dataEntrega?: string;
  criadoEm: string;
  atualizadoEm: string;
}

interface Alerta {
  id: number;
  tipo: string;
  titulo: string;
  descricao?: string;
  lido: boolean;
  link?: string | null;
  criadoEm: string;
}

// ── Config ─────────────────────────────────────────────────────────────────

const PRIO_CFG: Record<string, { label: string; cls: string; dot: string }> = {
  baixa:   { label: "Baixa",   cls: "text-slate-500",   dot: "bg-slate-400"   },
  normal:  { label: "Normal",  cls: "text-blue-600",    dot: "bg-blue-500"    },
  alta:    { label: "Alta",    cls: "text-amber-600",   dot: "bg-amber-500"   },
  urgente: { label: "Urgente", cls: "text-rose-600",    dot: "bg-rose-500"    },
};

const CAT_LABELS: Record<string, string> = {
  geral: "Geral", edital: "Edital", proposta: "Proposta",
  habilitacao: "Habilitação", recurso: "Recurso", contrato: "Contrato", disputa: "Disputa",
};

const STATUS_CFG: Record<string, { label: string; cls: string }> = {
  em_andamento: { label: "Em Andamento", cls: "bg-blue-500/10 text-blue-600 border-blue-500/20" },
  finalizada:   { label: "Finalizada",   cls: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20" },
  cancelada:    { label: "Cancelada",    cls: "bg-rose-500/10 text-rose-600 border-rose-500/20" },
};

const HAB_STATUS_CFG: Record<string, { label: string; cls: string; dot: string }> = {
  pendente:  { label: "Pendente",  cls: "bg-amber-500/10 text-amber-600 border-amber-500/30",    dot: "bg-amber-500"   },
  enviado:   { label: "Enviado",   cls: "bg-blue-500/10 text-blue-600 border-blue-500/30",       dot: "bg-blue-500"    },
  aprovado:  { label: "Aprovado",  cls: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30", dot: "bg-emerald-500" },
  rejeitado: { label: "Rejeitado", cls: "bg-rose-500/10 text-rose-600 border-rose-500/30",       dot: "bg-rose-500"    },
};

const DOCS_DEFAULT = [
  "Certidão de Regularidade do FGTS",
  "Certidão Negativa de Débitos — INSS / Receita Federal",
  "Certidão Negativa de Débitos Trabalhistas (CNDT)",
  "Certidão Negativa de Débitos Municipais",
  "Certidão Negativa de Débitos Estaduais",
  "Balanço Patrimonial",
  "Ato Constitutivo / Contrato Social",
  "Atestado de Capacidade Técnica",
];

function fmtValor(v?: number | string | null) {
  if (v == null) return null;
  const n = typeof v === "number" ? v : parseFloat(v);
  if (isNaN(n)) return String(v);
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function diasRestantes(iso?: string | null) {
  if (!iso) return null;
  return Math.ceil((new Date(iso).getTime() - Date.now()) / 86400000);
}

// ── Sub-components ─────────────────────────────────────────────────────────

function TarefaItem({
  t, gerId, onToggle, onDelete,
}: {
  t: Tarefa;
  gerId: number;
  onToggle: (id: number, concluida: boolean) => void;
  onDelete: (id: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const dias = diasRestantes(t.prazo);
  const atrasada = !t.concluida && dias !== null && dias < 0;
  const hoje = !t.concluida && dias !== null && dias === 0;
  const prio = PRIO_CFG[t.prioridade] ?? PRIO_CFG.normal;

  return (
    <div className={`border rounded-lg transition-all ${t.concluida ? "opacity-60 border-border" : atrasada ? "border-rose-300 bg-rose-50/40 dark:bg-rose-950/20" : hoje ? "border-amber-300 bg-amber-50/40 dark:bg-amber-950/20" : "border-border bg-card"}`}>
      <div className="flex items-start gap-3 p-3">
        <button
          onClick={() => onToggle(t.id, !t.concluida)}
          className={`mt-0.5 flex-shrink-0 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
            t.concluida ? "bg-emerald-500 border-emerald-500" : "border-muted-foreground hover:border-primary"
          }`}
        >
          {t.concluida && <CheckCircle2 className="w-3.5 h-3.5 text-white" />}
        </button>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-sm font-medium ${t.concluida ? "line-through text-muted-foreground" : "text-foreground"}`}>
              {t.titulo}
            </span>
            <span className={`text-xs flex items-center gap-1 ${prio.cls}`}>
              <span className={`w-2 h-2 rounded-full ${prio.dot}`} />
              {prio.label}
            </span>
            <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
              {CAT_LABELS[t.categoria] ?? t.categoria}
            </span>
            {t.prazo && (
              <span className={`text-xs flex items-center gap-1 ${atrasada ? "text-rose-600 font-semibold" : hoje ? "text-amber-600 font-semibold" : "text-muted-foreground"}`}>
                <Calendar className="w-3 h-3" />
                {fmtDateBRT(t.prazo + "T12:00:00")}
                {atrasada && " · Atrasada"}
                {hoje && " · Hoje"}
              </span>
            )}
          </div>
          {t.descricao && open && (
            <p className="text-xs text-muted-foreground mt-1 whitespace-pre-wrap">{t.descricao}</p>
          )}
        </div>

        <div className="flex items-center gap-1 flex-shrink-0">
          {t.descricao && (
            <button onClick={() => setOpen(v => !v)} className="p-1 text-muted-foreground hover:text-foreground">
              {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          )}
          <button onClick={() => onDelete(t.id)} className="p-1 text-muted-foreground hover:text-destructive transition-colors">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function GerenciamentoDetalhe() {
  // Extração do ID robusta: tenta (1) useParams, (2) useLocation relativa,
  // (3) window.location.pathname absoluta — para cobrir qualquer quirk do
  // wouter em Switch aninhado com catch-all /:rest*.
  const params = useParams<{ id: string }>();
  const [location, navigate] = useLocation();

  const gerId = (() => {
    // Tentativa 1 — params do wouter
    const fromParams = parseInt(params?.id ?? "", 10);
    if (!isNaN(fromParams) && fromParams > 0) return fromParams;

    // Tentativa 2 — useLocation relativa à base do Router ("/gerenciamento/9" → "9")
    const fromLocation = parseInt(
      location.split("/").filter(s => /^\d+$/.test(s)).pop() ?? "", 10
    );
    if (!isNaN(fromLocation) && fromLocation > 0) return fromLocation;

    // Tentativa 3 — window.location.pathname absoluta (infalível)
    const fromWindow = parseInt(
      window.location.pathname.split("/").filter(s => /^\d+$/.test(s)).pop() ?? "", 10
    );
    if (!isNaN(fromWindow) && fromWindow > 0) return fromWindow;

    console.error("[GerenciamentoDetalhe] Não foi possível extrair gerId", {
      paramsId: params?.id, location, pathname: window.location.pathname,
    });
    return 0;
  })();

  console.log("[GerenciamentoDetalhe] render — gerId:", gerId, "location:", location, "pathname:", window.location.pathname);
  const qc = useQueryClient();
  const { toast } = useToast();

  const [activeTab, setActiveTab] = useState<"tarefas" | "anotacoes" | "habilitacao">("tarefas");
  const [showFinalizarModal, setShowFinalizarModal] = useState(false);
  const [finalizarForm, setFinalizarForm] = useState({ resultado: "ganhou", valorProposta: "" });

  // Tarefa form
  const [novaTarefa, setNovaTarefa] = useState({ titulo: "", descricao: "", prazo: "", prioridade: "normal", categoria: "geral" });
  const [showTarefaForm, setShowTarefaForm] = useState(false);

  // Anotação form
  const [novaAnot, setNovaAnot] = useState("");
  const [editAnotId, setEditAnotId] = useState<number | null>(null);
  const [editAnotText, setEditAnotText] = useState("");

  // Habilitação form
  const [showHabForm, setShowHabForm] = useState(false);
  const [novaHab, setNovaHab] = useState({ documento: "", status: "pendente", observacoes: "", dataEntrega: "" });
  const [editHabId, setEditHabId] = useState<number | null>(null);
  const [editHab, setEditHab] = useState({ documento: "", status: "pendente", observacoes: "", dataEntrega: "" });

  // ── Queries ──────────────────────────────────────────────────────────────

  const { data: ger, isLoading } = useQuery<GerItem>({
    queryKey: ["gerenciamento", gerId],
    queryFn: async () => {
      const res = await apiFetch(`${BASE}/api/gerenciamento/${gerId}`, { credentials: "include" });
      if (!res.ok) throw new Error("Não encontrado");
      return res.json();
    },
    enabled: !!gerId,
  });

  const { data: tarefasData } = useQuery<{ data: Tarefa[] }>({
    queryKey: ["gerenciamento", gerId, "tarefas"],
    queryFn: async () => {
      const res = await apiFetch(`${BASE}/api/gerenciamento/${gerId}/tarefas`, { credentials: "include" });
      if (!res.ok) throw new Error();
      return res.json();
    },
    enabled: !!gerId,
  });

  const { data: anotacoesData } = useQuery<{ data: Anotacao[] }>({
    queryKey: ["gerenciamento", gerId, "anotacoes"],
    queryFn: async () => {
      const res = await apiFetch(`${BASE}/api/gerenciamento/${gerId}/anotacoes`, { credentials: "include" });
      if (!res.ok) throw new Error();
      return res.json();
    },
    enabled: !!gerId,
  });

  const { data: habilitacaoData } = useQuery<{ data: Habilitacao[] }>({
    queryKey: ["gerenciamento", gerId, "habilitacao"],
    queryFn: async () => {
      const res = await apiFetch(`${BASE}/api/gerenciamento/${gerId}/habilitacao`, { credentials: "include" });
      if (!res.ok) throw new Error();
      return res.json();
    },
    enabled: !!gerId,
  });

  // Local snapshot so the banner stays visible even after alerts are marked as read
  const [alertasSnap, setAlertasSnap] = React.useState<Alerta[]>([]);

  // Dismissed alert IDs kept in memory only. Cross-device sync is guaranteed
  // because the snapshot is only set AFTER the server confirms the mark-as-read
  // (see effect below), so on any other device the unread fetch returns empty.
  const [dismissedIds, setDismissedIds] = React.useState<Set<number>>(new Set());

  // On mount (and when gerId changes): fetch unread alerts → mark as read on server
  // → THEN set the snapshot. This ordering ensures the server state is committed
  // before the banner is rendered, so other devices see empty unread and no banner.
  React.useEffect(() => {
    if (!gerId) return;
    // Reset state for this ger
    setAlertasSnap([]);
    setDismissedIds(new Set());

    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch(`${BASE}/api/alertas?ger_id=${gerId}&lido=false`, { credentials: "include" });
        if (!res.ok || cancelled) return;
        const json = await res.json();
        const unread: Alerta[] = json.data ?? [];
        if (unread.length === 0 || cancelled) return;

        // Persist dismissal on server first
        await apiFetch(`${BASE}/api/alertas/ler-todos?ger_id=${gerId}`, {
          method: "POST", credentials: "include",
        });
        if (cancelled) return;

        // Only populate the banner after server confirms the read
        setAlertasSnap(unread);
        qc.invalidateQueries({ queryKey: ["alertas", "nao-lidos"] });
        qc.invalidateQueries({ queryKey: ["alertas-por-gerenciamento"] });
      } catch {
        // Banner is non-critical; swallow errors silently
      }
    })();

    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gerId]);

  // Hides the banner for the current session. Alerts are already marked read
  // on the server (above), so no further server call is needed.
  function dismissAlertas() {
    setDismissedIds(prev => {
      const next = new Set(prev);
      alertasSnap.forEach(a => next.add(a.id));
      return next;
    });
  }

  // ── Mutations ─────────────────────────────────────────────────────────────

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["gerenciamento", gerId] });
    qc.invalidateQueries({ queryKey: ["gerenciamento", gerId, "tarefas"] });
    qc.invalidateQueries({ queryKey: ["gerenciamento", gerId, "anotacoes"] });
    qc.invalidateQueries({ queryKey: ["gerenciamento", gerId, "habilitacao"] });
    qc.invalidateQueries({ queryKey: ["gerenciamento"] });
  };

  const updateGer = useMutation({
    mutationFn: async (body: object) => {
      const res = await apiFetch(`${BASE}/api/gerenciamento/${gerId}`, {
        method: "PATCH", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error();
      return res.json();
    },
    onSuccess: invalidate,
  });

  const deleteGer = useMutation({
    mutationFn: async () => {
      const res = await apiFetch(`${BASE}/api/gerenciamento/${gerId}`, { method: "DELETE", credentials: "include" });
      if (!res.ok && res.status !== 204) throw new Error();
    },
    onSuccess: () => navigate("/gerenciamento"),
  });

  const createTarefa = useMutation({
    mutationFn: async (body: object) => {
      const res = await apiFetch(`${BASE}/api/gerenciamento/${gerId}/tarefas`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(String(res.status));
      return res.json();
    },
    onSuccess: () => {
      invalidate();
      setNovaTarefa({ titulo: "", descricao: "", prazo: "", prioridade: "normal", categoria: "geral" });
      setShowTarefaForm(false);
    },
    onError: (err: unknown) => {
      const is401 = err instanceof Error && err.message === "401";
      toast({
        variant: "destructive",
        title: is401 ? "Sessão expirada" : "Erro ao salvar tarefa",
        description: is401
          ? "Faça login novamente para continuar."
          : "Não foi possível salvar a tarefa. Tente novamente.",
      });
    },
  });

  const toggleTarefa = useMutation({
    mutationFn: async ({ id, concluida }: { id: number; concluida: boolean }) => {
      const res = await apiFetch(`${BASE}/api/gerenciamento/${gerId}/tarefas/${id}`, {
        method: "PATCH", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ concluida }),
      });
      if (!res.ok) throw new Error(String(res.status));
    },
    onSuccess: invalidate,
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erro ao atualizar tarefa",
        description: "Não foi possível marcar a tarefa. Tente novamente.",
      });
    },
  });

  const deleteTarefa = useMutation({
    mutationFn: async (id: number) => {
      const res = await apiFetch(`${BASE}/api/gerenciamento/${gerId}/tarefas/${id}`, {
        method: "DELETE", credentials: "include",
      });
      if (!res.ok && res.status !== 204) throw new Error(String(res.status));
    },
    onSuccess: invalidate,
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erro ao excluir tarefa",
        description: "Não foi possível excluir a tarefa. Tente novamente.",
      });
    },
  });

  const createAnot = useMutation({
    mutationFn: async (conteudo: string) => {
      const res = await apiFetch(`${BASE}/api/gerenciamento/${gerId}/anotacoes`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conteudo }),
      });
      if (!res.ok) throw new Error();
      return res.json();
    },
    onSuccess: () => { invalidate(); setNovaAnot(""); },
  });

  const updateAnot = useMutation({
    mutationFn: async ({ id, conteudo }: { id: number; conteudo: string }) => {
      const res = await apiFetch(`${BASE}/api/gerenciamento/${gerId}/anotacoes/${id}`, {
        method: "PATCH", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conteudo }),
      });
      if (!res.ok) throw new Error();
    },
    onSuccess: () => { invalidate(); setEditAnotId(null); },
  });

  const deleteAnot = useMutation({
    mutationFn: async (id: number) => {
      const res = await apiFetch(`${BASE}/api/gerenciamento/${gerId}/anotacoes/${id}`, {
        method: "DELETE", credentials: "include",
      });
      if (!res.ok && res.status !== 204) throw new Error();
    },
    onSuccess: invalidate,
  });

  const createHab = useMutation({
    mutationFn: async (body: object) => {
      const res = await apiFetch(`${BASE}/api/gerenciamento/${gerId}/habilitacao`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error();
      return res.json();
    },
    onSuccess: () => {
      invalidate();
      setNovaHab({ documento: "", status: "pendente", observacoes: "", dataEntrega: "" });
      setShowHabForm(false);
    },
  });

  const updateHab = useMutation({
    mutationFn: async ({ id, ...body }: { id: number; [k: string]: unknown }) => {
      const res = await apiFetch(`${BASE}/api/gerenciamento/${gerId}/habilitacao/${id}`, {
        method: "PATCH", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error();
    },
    onSuccess: () => { invalidate(); setEditHabId(null); },
  });

  const deleteHab = useMutation({
    mutationFn: async (id: number) => {
      const res = await apiFetch(`${BASE}/api/gerenciamento/${gerId}/habilitacao/${id}`, {
        method: "DELETE", credentials: "include",
      });
      if (!res.ok && res.status !== 204) throw new Error();
    },
    onSuccess: invalidate,
  });

  // ── Render helpers ────────────────────────────────────────────────────────

  const tarefas = tarefasData?.data ?? [];
  const anotacoes = anotacoesData?.data ?? [];
  const habilitacoes = habilitacaoData?.data ?? [];
  const diasEnc = diasRestantes(ger?.licitacaoDataEncerramento);

  const habPendentes = habilitacoes.filter(h => h.status === "pendente").length;

  const tarefasAtrasadas = tarefas.filter(t => !t.concluida && diasRestantes(t.prazo) !== null && diasRestantes(t.prazo)! < 0).length;
  const tarefasHoje = tarefas.filter(t => !t.concluida && diasRestantes(t.prazo) === 0).length;

  if (isLoading) {
    return (
      <div style={{ minHeight: "50vh", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
           className="text-muted-foreground">
        <Loader2 className="w-5 h-5 animate-spin" />
        Carregando gerenciamento {gerId}…
      </div>
    );
  }

  if (!ger) {
    return (
      <div style={{ minHeight: "50vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16 }}>
        <p className="text-muted-foreground">
          {!gerId
            ? "ID inválido — acesse a partir da lista de licitações gerenciadas."
            : `Gerenciamento #${gerId} não encontrado.`}
        </p>
        <Link href="/gerenciamento" className="text-primary hover:underline text-sm">← Voltar à lista</Link>
      </div>
    );
  }

  const stCfg = STATUS_CFG[ger.status] ?? STATUS_CFG.em_andamento;

  return (
    <div className="flex flex-col min-h-0 flex-1">

      {/* ── Header ── */}
      <div className="px-6 py-4 border-b border-border flex-shrink-0">
        <div className="flex items-center gap-2 mb-3">
          <Link href="/gerenciamento"
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="w-4 h-4" />
            Gerenciadas
          </Link>
          <span className="text-muted-foreground/40">/</span>
          <span className="text-sm text-muted-foreground truncate max-w-xs">{ger.licitacaoNumero ?? `#${ger.id}`}</span>
        </div>

        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${stCfg.cls}`}>
                {stCfg.label}
              </span>
              {ger.licitacaoModalidade && (
                <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                  {ger.licitacaoModalidade}
                </span>
              )}
              {ger.resultado && (
                <span className={`text-xs px-2 py-0.5 rounded-full border font-medium flex items-center gap-1 ${
                  ger.resultado === "ganhou" ? "text-emerald-600 bg-emerald-50 border-emerald-200 dark:bg-emerald-950/30" :
                  ger.resultado === "perdeu" ? "text-rose-600 bg-rose-50 border-rose-200 dark:bg-rose-950/30" :
                  "text-amber-600 bg-amber-50 border-amber-200 dark:bg-amber-950/30"
                }`}>
                  <Trophy className="w-3 h-3" />
                  {ger.resultado === "ganhou" ? "Ganhou" : ger.resultado === "perdeu" ? "Perdeu" : "Desistiu"}
                  {ger.valorProposta ? ` · ${fmtValor(ger.valorProposta)}` : ""}
                </span>
              )}
            </div>
            <p className="text-base font-semibold text-foreground line-clamp-2">{ger.licitacaoObjeto}</p>
            <div className="flex flex-wrap gap-3 text-xs text-muted-foreground mt-2">
              {ger.licitacaoOrgao && <span className="flex items-center gap-1"><Building2 className="w-3 h-3" />{ger.licitacaoOrgao}</span>}
              {(ger.licitacaoMunicipio || ger.licitacaoUf) && (
                <span className="flex items-center gap-1"><MapPin className="w-3 h-3" />{[ger.licitacaoMunicipio, ger.licitacaoUf].filter(Boolean).join("/")}</span>
              )}
              {ger.licitacaoDataEncerramento && (
                <span className={`flex items-center gap-1 ${diasEnc !== null && diasEnc <= 3 && diasEnc >= 0 ? "text-rose-500 font-semibold" : ""}`}>
                  <Calendar className="w-3 h-3" />
                  Encerra: {fmtDateBRT(ger.licitacaoDataEncerramento)}
                  {diasEnc !== null && diasEnc >= 0 && ` (${diasEnc}d)`}
                  {diasEnc !== null && diasEnc < 0 && " (encerrada)"}
                </span>
              )}
              {ger.licitacaoValor && (
                <span className="flex items-center gap-1 font-medium text-foreground">
                  <TrendingUp className="w-3 h-3 text-primary" />
                  {fmtValor(ger.licitacaoValor)}
                </span>
              )}
              {gerarUrlPncp(ger.licitacaoNumero) && (
                <a href={gerarUrlPncp(ger.licitacaoNumero)!} target="_blank" rel="noreferrer"
                  className="flex items-center gap-1 text-primary hover:underline">
                  <ExternalLink className="w-3 h-3" />
                  Ver no PNCP
                </a>
              )}
            </div>
          </div>

          {/* Ações */}
          <div className="flex items-center gap-2 flex-shrink-0">
            {ger.status === "em_andamento" && (
              <button
                onClick={() => setShowFinalizarModal(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 transition-colors"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                Finalizar
              </button>
            )}
            <button
              onClick={() => { if (confirm("Remover esta licitação do gerenciamento?")) deleteGer.mutate(); }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-destructive/40 text-destructive text-xs font-semibold hover:bg-destructive/10 transition-colors"
            >
              <XCircle className="w-3.5 h-3.5" />
              Remover
            </button>
          </div>
        </div>

        {/* Contadores rápidos */}
        <div className="flex gap-4 mt-3 pt-3 border-t border-border/60 text-xs text-muted-foreground flex-wrap">
          <span className="flex items-center gap-1.5">
            <CheckSquare className="w-3.5 h-3.5" />
            {ger.tarefasConcluidas}/{ger.totalTarefas} tarefas
          </span>
          {tarefasAtrasadas > 0 && (
            <span className="flex items-center gap-1.5 text-rose-500 font-semibold">
              <AlertTriangle className="w-3.5 h-3.5" />
              {tarefasAtrasadas} atrasada{tarefasAtrasadas !== 1 ? "s" : ""}
            </span>
          )}
          {tarefasHoje > 0 && (
            <span className="flex items-center gap-1.5 text-amber-500 font-semibold">
              <Clock className="w-3.5 h-3.5" />
              {tarefasHoje} para hoje
            </span>
          )}
          <span className="flex items-center gap-1.5">
            <StickyNote className="w-3.5 h-3.5" />
            {ger.totalAnotacoes} anotaç{ger.totalAnotacoes !== 1 ? "ões" : "ão"}
          </span>
          <span>Gerenciada desde {fmtDateBRT(ger.criadoEm)}</span>
        </div>
      </div>

      {/* ── Alertas de prazo ── */}
      {(() => {
        const alertasVisiveis = alertasSnap.filter(a => !dismissedIds.has(a.id));
        if (alertasVisiveis.length === 0) return null;
        const urgentes = alertasVisiveis.filter(a => a.tipo === "tarefa_vencida");
        return (
          <div className="mx-6 mt-3 mb-0 rounded-lg border border-amber-300 bg-amber-50/60 dark:bg-amber-950/20 dark:border-amber-700 flex-shrink-0">
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-amber-200 dark:border-amber-800">
              <BellRing className="w-4 h-4 text-amber-600 flex-shrink-0" />
              <span className="text-sm font-semibold text-amber-800 dark:text-amber-300">
                {alertasVisiveis.length === 1
                  ? "1 alerta de prazo"
                  : `${alertasVisiveis.length} alertas de prazo`}
              </span>
              {urgentes.length > 0 && (
                <span className="text-xs font-semibold text-rose-600 bg-rose-100 dark:bg-rose-950/40 px-2 py-0.5 rounded-full">
                  {urgentes.length} vencida{urgentes.length !== 1 ? "s" : ""}
                </span>
              )}
              <button
                onClick={dismissAlertas}
                className="ml-auto p-0.5 text-amber-500 hover:text-amber-800 dark:hover:text-amber-300 transition-colors"
                aria-label="Fechar alertas"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <ul className="divide-y divide-amber-100 dark:divide-amber-900">
              {alertasVisiveis.map(a => (
                <li key={a.id} className="px-4 py-2 flex items-start gap-2">
                  <span className="mt-0.5 flex-shrink-0 text-base leading-none">
                    {a.tipo === "tarefa_vencida" ? "🚨" : a.tipo === "tarefa_prazo_1d" ? "⚠️" : "⏰"}
                  </span>
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-foreground leading-snug">{a.titulo}</p>
                    {a.descricao && (
                      <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{a.descricao}</p>
                    )}
                  </div>
                </li>
              ))}
            </ul>
            <div className="px-4 py-2 flex justify-end border-t border-amber-200 dark:border-amber-800">
              <button
                onClick={dismissAlertas}
                className="text-xs font-semibold text-amber-800 dark:text-amber-300 hover:text-amber-900 dark:hover:text-amber-100 px-3 py-1 rounded-md hover:bg-amber-100 dark:hover:bg-amber-900/40 transition-colors"
              >
                Entendido
              </button>
            </div>
          </div>
        );
      })()}

      {/* ── Tabs ── */}
      <div className="border-b border-border flex-shrink-0 px-6 mt-3">
        <div className="flex gap-1">
          <button
            onClick={() => setActiveTab("tarefas")}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === "tarefas" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}
          >
            <span className="flex items-center gap-1.5">
              <CheckSquare className="w-4 h-4" />
              Tarefas
              {tarefas.length > 0 && (
                <span className="text-xs bg-primary/10 text-primary px-1.5 py-0.5 rounded-full">
                  {tarefas.filter(t => !t.concluida).length}
                </span>
              )}
            </span>
          </button>

          <button
            onClick={() => setActiveTab("anotacoes")}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === "anotacoes" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}
          >
            <span className="flex items-center gap-1.5">
              <StickyNote className="w-4 h-4" />
              Anotações
              {anotacoes.length > 0 && (
                <span className="text-xs bg-primary/10 text-primary px-1.5 py-0.5 rounded-full">
                  {anotacoes.length}
                </span>
              )}
            </span>
          </button>

          <button
            onClick={() => setActiveTab("habilitacao")}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === "habilitacao" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}
          >
            <span className="flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4" />
              Habilitação
              {habPendentes > 0 && (
                <span className="text-xs bg-amber-500/10 text-amber-600 px-1.5 py-0.5 rounded-full">
                  {habPendentes}
                </span>
              )}
            </span>
          </button>
        </div>
      </div>

      {/* ── Content ── */}
      <div className="flex-1 overflow-y-auto px-6 py-4">

        {/* ── Aba Tarefas ── */}
        {activeTab === "tarefas" && (
          <div className="space-y-3 max-w-3xl">
            {/* Filtros por estado */}
            {tarefas.length > 0 && (
              <div className="flex gap-4 text-xs py-1">
                {[
                  { label: `Atrasadas (${tarefasAtrasadas})`,       cls: "text-rose-500"    },
                  { label: `Hoje (${tarefasHoje})`,                  cls: "text-amber-500"   },
                  { label: `Concluídas (${tarefas.filter(t => t.concluida).length})`, cls: "text-emerald-600" },
                ].map(f => (
                  <span key={f.label} className={`font-medium ${f.cls}`}>{f.label}</span>
                ))}
              </div>
            )}

            {/* Form nova tarefa */}
            {showTarefaForm ? (
              <div className="bg-muted/30 border border-border rounded-xl p-4 space-y-3">
                <p className="text-sm font-semibold text-foreground">Nova Tarefa</p>
                <input
                  value={novaTarefa.titulo}
                  onChange={e => setNovaTarefa(p => ({ ...p, titulo: e.target.value }))}
                  placeholder="Título da tarefa *"
                  className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
                <textarea
                  value={novaTarefa.descricao}
                  onChange={e => setNovaTarefa(p => ({ ...p, descricao: e.target.value }))}
                  placeholder="Descrição (opcional)"
                  rows={2}
                  className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
                />
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">Prazo</label>
                    <input
                      type="date"
                      value={novaTarefa.prazo}
                      onChange={e => setNovaTarefa(p => ({ ...p, prazo: e.target.value }))}
                      className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">Prioridade</label>
                    <select
                      value={novaTarefa.prioridade}
                      onChange={e => setNovaTarefa(p => ({ ...p, prioridade: e.target.value }))}
                      className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                    >
                      {Object.entries(PRIO_CFG).map(([v, c]) => <option key={v} value={v}>{c.label}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">Categoria</label>
                    <select
                      value={novaTarefa.categoria}
                      onChange={e => setNovaTarefa(p => ({ ...p, categoria: e.target.value }))}
                      className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                    >
                      {Object.entries(CAT_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                    </select>
                  </div>
                </div>
                <div className="flex gap-2 justify-end">
                  <button
                    onClick={() => { setShowTarefaForm(false); setNovaTarefa({ titulo: "", descricao: "", prazo: "", prioridade: "normal", categoria: "geral" }); }}
                    className="px-3 py-1.5 text-sm border border-border rounded-lg hover:bg-muted transition-colors"
                  >
                    Cancelar
                  </button>
                  <button
                    disabled={!novaTarefa.titulo.trim() || createTarefa.isPending}
                    onClick={() => createTarefa.mutate({
                      titulo: novaTarefa.titulo.trim(),
                      descricao: novaTarefa.descricao || null,
                      prazo: novaTarefa.prazo || null,
                      prioridade: novaTarefa.prioridade,
                      categoria: novaTarefa.categoria,
                    })}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50"
                  >
                    {createTarefa.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                    Salvar
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setShowTarefaForm(true)}
                className="flex items-center gap-2 px-4 py-2.5 w-full border border-dashed border-border rounded-xl text-sm text-muted-foreground hover:text-foreground hover:border-primary/40 hover:bg-muted/40 transition-colors"
              >
                <Plus className="w-4 h-4" />
                Adicionar tarefa
              </button>
            )}

            {/* Lista de tarefas */}
            {tarefas.length === 0 ? (
              <div className="text-center py-10 text-muted-foreground">
                <CheckSquare className="w-8 h-8 mx-auto mb-2 opacity-40" />
                <p className="text-sm">Nenhuma tarefa cadastrada.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {/* Pendentes primeiro */}
                {tarefas.filter(t => !t.concluida).map(t => (
                  <TarefaItem key={t.id} t={t} gerId={gerId}
                    onToggle={(id, c) => toggleTarefa.mutate({ id, concluida: c })}
                    onDelete={(id) => deleteTarefa.mutate(id)}
                  />
                ))}
                {/* Concluídas */}
                {tarefas.filter(t => t.concluida).length > 0 && (
                  <>
                    <p className="text-xs text-muted-foreground pt-2 pb-1">Concluídas</p>
                    {tarefas.filter(t => t.concluida).map(t => (
                      <TarefaItem key={t.id} t={t} gerId={gerId}
                        onToggle={(id, c) => toggleTarefa.mutate({ id, concluida: c })}
                        onDelete={(id) => deleteTarefa.mutate(id)}
                      />
                    ))}
                  </>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── Aba Habilitação ── */}
        {activeTab === "habilitacao" && (
          <div className="space-y-3 max-w-3xl">
            {/* Form novo documento */}
            {showHabForm ? (
              <div className="bg-muted/30 border border-border rounded-xl p-4 space-y-3">
                <p className="text-sm font-semibold text-foreground">Novo Documento</p>

                {/* Sugestões de documentos típicos */}
                {!novaHab.documento && (
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground">Documentos típicos:</p>
                    <div className="flex flex-wrap gap-1.5">
                      {DOCS_DEFAULT.map(doc => (
                        <button
                          key={doc}
                          onClick={() => setNovaHab(p => ({ ...p, documento: doc }))}
                          className="text-xs px-2 py-1 border border-border rounded-lg bg-background hover:bg-muted hover:border-primary/40 transition-colors text-left"
                        >
                          {doc}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <input
                  value={novaHab.documento}
                  onChange={e => setNovaHab(p => ({ ...p, documento: e.target.value }))}
                  placeholder="Nome do documento *"
                  className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                />

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">Status</label>
                    <select
                      value={novaHab.status}
                      onChange={e => setNovaHab(p => ({ ...p, status: e.target.value }))}
                      className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                    >
                      {Object.entries(HAB_STATUS_CFG).map(([v, c]) => (
                        <option key={v} value={v}>{c.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">Data de entrega</label>
                    <input
                      type="date"
                      value={novaHab.dataEntrega}
                      onChange={e => setNovaHab(p => ({ ...p, dataEntrega: e.target.value }))}
                      className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                    />
                  </div>
                </div>

                <textarea
                  value={novaHab.observacoes}
                  onChange={e => setNovaHab(p => ({ ...p, observacoes: e.target.value }))}
                  placeholder="Observações (opcional)"
                  rows={2}
                  className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
                />

                <div className="flex gap-2 justify-end">
                  <button
                    onClick={() => { setShowHabForm(false); setNovaHab({ documento: "", status: "pendente", observacoes: "", dataEntrega: "" }); }}
                    className="px-3 py-1.5 text-sm border border-border rounded-lg hover:bg-muted transition-colors"
                  >
                    Cancelar
                  </button>
                  <button
                    disabled={!novaHab.documento.trim() || createHab.isPending}
                    onClick={() => createHab.mutate({
                      documento: novaHab.documento.trim(),
                      status: novaHab.status,
                      observacoes: novaHab.observacoes || null,
                      dataEntrega: novaHab.dataEntrega || null,
                    })}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50"
                  >
                    {createHab.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                    Salvar
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setShowHabForm(true)}
                className="flex items-center gap-2 px-4 py-2.5 w-full border border-dashed border-border rounded-xl text-sm text-muted-foreground hover:text-foreground hover:border-primary/40 hover:bg-muted/40 transition-colors"
              >
                <Plus className="w-4 h-4" />
                Adicionar documento
              </button>
            )}

            {/* Lista de documentos */}
            {habilitacoes.length === 0 ? (
              <div className="text-center py-10 text-muted-foreground">
                <ShieldCheck className="w-8 h-8 mx-auto mb-2 opacity-40" />
                <p className="text-sm">Nenhum documento cadastrado.</p>
                <p className="text-xs mt-1">Adicione documentos de habilitação para acompanhar o envio.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {habilitacoes.map(h => {
                  const stCfgH = HAB_STATUS_CFG[h.status] ?? HAB_STATUS_CFG.pendente;
                  return (
                    <div key={h.id} className="bg-card border border-border rounded-xl p-4">
                      {editHabId === h.id ? (
                        <div className="space-y-3">
                          <input
                            value={editHab.documento}
                            onChange={e => setEditHab(p => ({ ...p, documento: e.target.value }))}
                            placeholder="Nome do documento"
                            className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                          />
                          <div className="grid grid-cols-2 gap-3">
                            <div>
                              <label className="text-xs text-muted-foreground mb-1 block">Status</label>
                              <select
                                value={editHab.status}
                                onChange={e => setEditHab(p => ({ ...p, status: e.target.value }))}
                                className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                              >
                                {Object.entries(HAB_STATUS_CFG).map(([v, c]) => (
                                  <option key={v} value={v}>{c.label}</option>
                                ))}
                              </select>
                            </div>
                            <div>
                              <label className="text-xs text-muted-foreground mb-1 block">Data de entrega</label>
                              <input
                                type="date"
                                value={editHab.dataEntrega}
                                onChange={e => setEditHab(p => ({ ...p, dataEntrega: e.target.value }))}
                                className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                              />
                            </div>
                          </div>
                          <textarea
                            value={editHab.observacoes}
                            onChange={e => setEditHab(p => ({ ...p, observacoes: e.target.value }))}
                            placeholder="Observações"
                            rows={2}
                            className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
                          />
                          <div className="flex gap-2 justify-end">
                            <button onClick={() => setEditHabId(null)} className="px-3 py-1.5 text-xs border border-border rounded-lg hover:bg-muted">Cancelar</button>
                            <button
                              disabled={!editHab.documento.trim() || updateHab.isPending}
                              onClick={() => updateHab.mutate({
                                id: h.id,
                                documento: editHab.documento.trim(),
                                status: editHab.status,
                                observacoes: editHab.observacoes || null,
                                dataEntrega: editHab.dataEntrega || null,
                              })}
                              className="flex items-center gap-1 px-3 py-1.5 text-xs bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50"
                            >
                              <Save className="w-3 h-3" /> Salvar
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-start gap-3">
                          <FileCheck className="w-4 h-4 mt-0.5 flex-shrink-0 text-muted-foreground" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-sm font-medium text-foreground">{h.documento}</span>
                              <span className={`text-xs px-2 py-0.5 rounded-full border font-medium flex items-center gap-1 ${stCfgH.cls}`}>
                                <span className={`w-1.5 h-1.5 rounded-full ${stCfgH.dot}`} />
                                {stCfgH.label}
                              </span>
                              {h.dataEntrega && (
                                <span className="text-xs text-muted-foreground flex items-center gap-1">
                                  <Calendar className="w-3 h-3" />
                                  {fmtDateBRT(h.dataEntrega + "T12:00:00")}
                                </span>
                              )}
                            </div>
                            {h.observacoes && (
                              <p className="text-xs text-muted-foreground mt-1 whitespace-pre-wrap">{h.observacoes}</p>
                            )}
                          </div>
                          <div className="flex items-center gap-1 flex-shrink-0">
                            <button
                              onClick={() => {
                                setEditHabId(h.id);
                                setEditHab({
                                  documento: h.documento,
                                  status: h.status,
                                  observacoes: h.observacoes ?? "",
                                  dataEntrega: h.dataEntrega ?? "",
                                });
                              }}
                              className="p-1.5 text-muted-foreground hover:text-foreground transition-colors"
                            >
                              <Edit3 className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => deleteHab.mutate(h.id)}
                              className="p-1.5 text-muted-foreground hover:text-destructive transition-colors"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Resumo de status */}
            {habilitacoes.length > 0 && (
              <div className="flex gap-4 text-xs pt-1">
                {Object.entries(HAB_STATUS_CFG).map(([key, cfg]) => {
                  const count = habilitacoes.filter(h => h.status === key).length;
                  if (count === 0) return null;
                  return (
                    <span key={key} className={`font-medium flex items-center gap-1 ${cfg.cls.split(" ").find(c => c.startsWith("text-")) ?? "text-muted-foreground"}`}>
                      <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
                      {cfg.label}: {count}
                    </span>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ── Aba Anotações ── */}
        {activeTab === "anotacoes" && (
          <div className="space-y-3 max-w-3xl">
            {/* Input nova anotação */}
            <div className="bg-muted/30 border border-border rounded-xl p-4">
              <textarea
                value={novaAnot}
                onChange={e => setNovaAnot(e.target.value)}
                placeholder="Escreva uma anotação…"
                rows={3}
                className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
              />
              <div className="flex justify-end mt-2">
                <button
                  disabled={!novaAnot.trim() || createAnot.isPending}
                  onClick={() => createAnot.mutate(novaAnot.trim())}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  {createAnot.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                  Adicionar
                </button>
              </div>
            </div>

            {/* Lista de anotações */}
            {anotacoes.length === 0 ? (
              <div className="text-center py-10 text-muted-foreground">
                <StickyNote className="w-8 h-8 mx-auto mb-2 opacity-40" />
                <p className="text-sm">Nenhuma anotação ainda.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {anotacoes.map(a => (
                  <div key={a.id} className="bg-card border border-border rounded-xl p-4">
                    {editAnotId === a.id ? (
                      <>
                        <textarea
                          value={editAnotText}
                          onChange={e => setEditAnotText(e.target.value)}
                          rows={3}
                          className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
                        />
                        <div className="flex gap-2 justify-end mt-2">
                          <button onClick={() => setEditAnotId(null)} className="px-3 py-1.5 text-xs border border-border rounded-lg hover:bg-muted">Cancelar</button>
                          <button
                            disabled={!editAnotText.trim() || updateAnot.isPending}
                            onClick={() => updateAnot.mutate({ id: a.id, conteudo: editAnotText.trim() })}
                            className="flex items-center gap-1 px-3 py-1.5 text-xs bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50"
                          >
                            <Save className="w-3 h-3" /> Salvar
                          </button>
                        </div>
                      </>
                    ) : (
                      <div className="flex items-start gap-3">
                        <div className="flex-1">
                          <p className="text-sm text-foreground whitespace-pre-wrap">{a.conteudo}</p>
                          <p className="text-xs text-muted-foreground mt-2">{fmtDateTime(a.criadoEm)}</p>
                        </div>
                        <div className="flex items-center gap-1 flex-shrink-0">
                          <button
                            onClick={() => { setEditAnotId(a.id); setEditAnotText(a.conteudo); }}
                            className="p-1.5 text-muted-foreground hover:text-foreground transition-colors"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => deleteAnot.mutate(a.id)}
                            className="p-1.5 text-muted-foreground hover:text-destructive transition-colors"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Modal Finalizar ── */}
      {showFinalizarModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-sm p-6">
            <h3 className="text-base font-bold text-foreground mb-4 flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-500" />
              Finalizar Gerenciamento
            </h3>
            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium text-foreground block mb-1">Resultado</label>
                <select
                  value={finalizarForm.resultado}
                  onChange={e => setFinalizarForm(p => ({ ...p, resultado: e.target.value }))}
                  className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                >
                  <option value="ganhou">🏆 Ganhou</option>
                  <option value="perdeu">❌ Perdeu</option>
                  <option value="desistiu">⚠️ Desistiu</option>
                </select>
              </div>
              {finalizarForm.resultado === "ganhou" && (
                <div>
                  <label className="text-sm font-medium text-foreground block mb-1">Valor da Proposta (R$)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={finalizarForm.valorProposta}
                    onChange={e => setFinalizarForm(p => ({ ...p, valorProposta: e.target.value }))}
                    placeholder="Ex: 150000.00"
                    className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                  />
                </div>
              )}
            </div>
            <div className="flex gap-2 mt-5">
              <button onClick={() => setShowFinalizarModal(false)} className="flex-1 px-4 py-2 text-sm border border-border rounded-lg hover:bg-muted">
                Cancelar
              </button>
              <button
                disabled={updateGer.isPending}
                onClick={() => {
                  updateGer.mutate({
                    status: "finalizada",
                    resultado: finalizarForm.resultado,
                    valorProposta: finalizarForm.valorProposta ? parseFloat(finalizarForm.valorProposta) : null,
                  });
                  setShowFinalizarModal(false);
                }}
                className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2 text-sm bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50"
              >
                {updateGer.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
