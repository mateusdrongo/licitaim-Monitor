import React, { useState, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  FileText, Upload, Search, Filter, Download, Trash2, Eye,
  Plus, X, CheckCircle, Clock, AlertCircle, ChevronDown, FileUp,
} from "lucide-react";
import { apiFetch } from "@/lib/apiFetch";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

// ─── Types ────────────────────────────────────────────────────────────────────
interface Documento {
  id: number;
  nome: string;
  grupo: string;
  situacao: "disponivel" | "pendente" | "coletando";
  tipoAtualizacao: "manual" | "auto";
  dataVencimento: string | null;
  url: string | null;
  tamanho: number | null;
  tipo: string | null;
  descricao: string | null;
  criadoEm: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────
const GRUPOS = [
  "Habilitação Jurídica",
  "Regularidade Fiscal, Social e Trabalhista",
  "Qualificação Técnica",
  "Qualificação Econômica Financeira",
  "Outros",
];

const SITUACAO_CONFIG = {
  disponivel: { label: "Disponível", color: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400", icon: CheckCircle },
  pendente:   { label: "Pendente",   color: "bg-amber-500/10 text-amber-700 dark:text-amber-400",   icon: Clock },
  coletando:  { label: "Coletando",  color: "bg-blue-500/10 text-blue-700 dark:text-blue-400",       icon: AlertCircle },
};

// ─── API helpers ──────────────────────────────────────────────────────────────
async function fetchDocumentos(params: {
  grupo?: string; situacao?: string; tipoAtualizacao?: string; q?: string;
}) {
  const sp = new URLSearchParams();
  if (params.grupo)           sp.set("grupo", params.grupo);
  if (params.situacao)        sp.set("situacao", params.situacao);
  if (params.tipoAtualizacao) sp.set("tipo_atualizacao", params.tipoAtualizacao);
  if (params.q)               sp.set("q", params.q);
  const res = await apiFetch(`${BASE}/api/documentos?${sp}`, { credentials: "include" });
  if (!res.ok) throw new Error("Erro ao buscar documentos");
  return res.json() as Promise<{ data: Documento[]; total: number }>;
}

async function uploadDocumento(form: FormData) {
  const res = await apiFetch(`${BASE}/api/documentos/upload`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as any).detail || "Erro ao enviar documento");
  }
  return res.json() as Promise<Documento>;
}

async function deleteDocumento(id: number) {
  const res = await apiFetch(`${BASE}/api/documentos/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Erro ao remover documento");
}

// ─── Upload Dialog ────────────────────────────────────────────────────────────
function UploadDialog({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [nome, setNome] = useState("");
  const [grupo, setGrupo] = useState(GRUPOS[1]);
  const [situacao, setSituacao] = useState("disponivel");
  const [dataVencimento, setDataVencimento] = useState("");
  const [descricao, setDescricao] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const mutation = useMutation({
    mutationFn: uploadDocumento,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documentos"] });
      onClose();
    },
    onError: (e: Error) => setError(e.message),
  });

  const handleFile = (f: File) => {
    setFile(f);
    if (!nome) setNome(f.name.replace(/\.[^/.]+$/, ""));
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) { setError("Selecione um arquivo."); return; }
    if (!nome.trim()) { setError("Informe o nome do documento."); return; }
    const form = new FormData();
    form.append("file", file);
    form.append("nome", nome.trim());
    form.append("grupo", grupo);
    form.append("situacao", situacao);
    form.append("tipo_atualizacao", "manual");
    if (dataVencimento) form.append("data_vencimento", dataVencimento);
    if (descricao) form.append("descricao", descricao);
    setError("");
    mutation.mutate(form);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-card border border-border rounded-2xl shadow-2xl w-full max-w-lg mx-4 p-6 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <FileUp className="w-5 h-5 text-primary" /> Adicionar Documento
          </h2>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-muted transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors
              ${dragOver ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-muted/40"}`}
          >
            <input
              ref={fileRef}
              type="file"
              className="hidden"
              accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
            />
            {file ? (
              <div className="space-y-1">
                <FileText className="w-8 h-8 text-primary mx-auto" />
                <p className="font-medium text-sm">{file.name}</p>
                <p className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(1)} KB</p>
              </div>
            ) : (
              <div className="space-y-2">
                <Upload className="w-8 h-8 text-muted-foreground mx-auto" />
                <p className="text-sm font-medium">Arraste ou clique para selecionar</p>
                <p className="text-xs text-muted-foreground">PDF, DOC, DOCX, XLS, XLSX, PNG, JPG</p>
              </div>
            )}
          </div>

          {/* Nome */}
          <div>
            <label className="block text-sm font-medium mb-1">Nome do documento <span className="text-red-500">*</span></label>
            <input
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              placeholder="Ex: Certidão Negativa Federal"
            />
          </div>

          {/* Grupo */}
          <div>
            <label className="block text-sm font-medium mb-1">Grupo</label>
            <select
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              value={grupo}
              onChange={(e) => setGrupo(e.target.value)}
            >
              {GRUPOS.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Situação */}
            <div>
              <label className="block text-sm font-medium mb-1">Situação</label>
              <select
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                value={situacao}
                onChange={(e) => setSituacao(e.target.value)}
              >
                <option value="disponivel">Disponível</option>
                <option value="pendente">Pendente</option>
                <option value="coletando">Coletando</option>
              </select>
            </div>

            {/* Vencimento */}
            <div>
              <label className="block text-sm font-medium mb-1">Data de vencimento</label>
              <input
                type="date"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                value={dataVencimento}
                onChange={(e) => setDataVencimento(e.target.value)}
              />
            </div>
          </div>

          {/* Descrição */}
          <div>
            <label className="block text-sm font-medium mb-1">Observação</label>
            <textarea
              rows={2}
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none"
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              placeholder="Opcional"
            />
          </div>

          {error && <p className="text-sm text-red-600 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg px-3 py-2">{error}</p>}

          <div className="flex justify-end gap-3 pt-1">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-muted transition-colors">
              Cancelar
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="px-5 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 disabled:opacity-60 transition-opacity flex items-center gap-2"
            >
              {mutation.isPending ? (
                <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Enviando...</>
              ) : (
                <><Upload className="w-4 h-4" /> Enviar Documento</>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Checkbox filter toggle helper ───────────────────────────────────────────
function toggleSet<T>(set: Set<T>, value: T): Set<T> {
  const next = new Set(set);
  next.has(value) ? next.delete(value) : next.add(value);
  return next;
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function Documentos() {
  const qc = useQueryClient();
  const [showUpload, setShowUpload] = useState(false);
  const [q, setQ] = useState("");
  const [filterGrupos, setFilterGrupos] = useState<Set<string>>(new Set());
  const [filterSituacoes, setFilterSituacoes] = useState<Set<string>>(new Set());
  const [filterTipos, setFilterTipos] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  // Fetch all; filtering done client-side so checkboxes can combine freely
  const { data, isLoading } = useQuery({
    queryKey: ["documentos"],
    queryFn: () => fetchDocumentos({ q: "" }),
  });

  const deleteMut = useMutation({
    mutationFn: deleteDocumento,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documentos"] });
      setConfirmDelete(null);
      setSelected(prev => { const n = new Set(prev); n.delete(confirmDelete!); return n; });
    },
  });

  const allDocs = data?.data ?? [];

  // Client-side filtering
  const docs = allDocs.filter(doc => {
    if (q && !doc.nome.toLowerCase().includes(q.toLowerCase())) return false;
    if (filterGrupos.size > 0 && !filterGrupos.has(doc.grupo)) return false;
    if (filterSituacoes.size > 0 && !filterSituacoes.has(doc.situacao)) return false;
    if (filterTipos.size > 0 && !filterTipos.has(doc.tipoAtualizacao)) return false;
    return true;
  });

  const total = docs.length;
  const hasFilters = !!(q || filterGrupos.size || filterSituacoes.size || filterTipos.size);

  const toggleSelect = (id: number) =>
    setSelected(prev => toggleSet(prev, id));

  const toggleSelectAll = () => {
    if (selected.size === docs.length && docs.length > 0) {
      setSelected(new Set());
    } else {
      setSelected(new Set(docs.map(d => d.id)));
    }
  };

  const clearFilters = () => {
    setFilterGrupos(new Set());
    setFilterSituacoes(new Set());
    setFilterTipos(new Set());
    setQ("");
  };

  // Download all selected that have a URL
  const downloadSelected = () => {
    const toDownload = docs.filter(d => selected.has(d.id) && d.url);
    toDownload.forEach((doc, i) => {
      setTimeout(() => {
        const a = document.createElement("a");
        a.href = `${BASE}${doc.url}`;
        a.download = doc.nome;
        a.target = "_blank";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      }, i * 300); // stagger to avoid browser blocking
    });
  };

  const formatDate = (d: string | null) => {
    if (!d) return "—";
    try { return new Date(d + "T12:00:00").toLocaleDateString("pt-BR"); }
    catch { return d; }
  };

  const isVencendo = (d: string | null) => {
    if (!d) return false;
    const diff = (new Date(d).getTime() - Date.now()) / 86400000;
    return diff >= 0 && diff <= 30;
  };

  const isVencido = (d: string | null) => {
    if (!d) return false;
    return new Date(d + "T12:00:00").getTime() < Date.now();
  };

  const selectedWithUrl = docs.filter(d => selected.has(d.id) && d.url).length;
  const allSelected = docs.length > 0 && selected.size === docs.length;
  const someSelected = selected.size > 0 && !allSelected;

  return (
    <div className="flex h-full min-h-screen bg-background">
      {/* ── Sidebar de filtros ── */}
      <aside className="hidden lg:flex flex-col w-64 flex-shrink-0 border-r border-border p-5 gap-6 bg-card">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-sm flex items-center gap-2">
            <Filter className="w-4 h-4 text-muted-foreground" /> Filtros
          </h3>
          {hasFilters && (
            <button onClick={clearFilters} className="text-xs text-primary hover:underline">Limpar</button>
          )}
        </div>

        {/* Busca */}
        <div>
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2 block">Busca</label>
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-muted-foreground" />
            <input
              className="w-full pl-8 pr-3 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="Buscar..."
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
        </div>

        {/* Grupos — checkbox */}
        <div>
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2 block">Grupos de Documentos</label>
          <div className="space-y-1.5">
            {GRUPOS.map(g => (
              <label key={g} className="flex items-start gap-2 cursor-pointer text-sm hover:text-foreground text-muted-foreground">
                <input
                  type="checkbox"
                  className="accent-primary mt-0.5 flex-shrink-0"
                  checked={filterGrupos.has(g)}
                  onChange={() => setFilterGrupos(prev => toggleSet(prev, g))}
                />
                <span className="leading-snug">{g}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Situação — checkbox */}
        <div>
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2 block">Situação</label>
          <div className="space-y-1.5">
            {(["disponivel", "pendente", "coletando"] as const).map(s => (
              <label key={s} className="flex items-center gap-2 cursor-pointer text-sm hover:text-foreground text-muted-foreground">
                <input
                  type="checkbox"
                  className="accent-primary"
                  checked={filterSituacoes.has(s)}
                  onChange={() => setFilterSituacoes(prev => toggleSet(prev, s))}
                />
                {SITUACAO_CONFIG[s].label}
              </label>
            ))}
          </div>
        </div>

        {/* Forma de atualização — checkbox */}
        <div>
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2 block">Forma de Atualização</label>
          <div className="space-y-1.5">
            {[["manual", "Manual"], ["auto", "Automático"]].map(([val, lbl]) => (
              <label key={val} className="flex items-center gap-2 cursor-pointer text-sm hover:text-foreground text-muted-foreground">
                <input
                  type="checkbox"
                  className="accent-primary"
                  checked={filterTipos.has(val)}
                  onChange={() => setFilterTipos(prev => toggleSet(prev, val))}
                />
                {lbl}
              </label>
            ))}
          </div>
        </div>
      </aside>

      {/* ── Conteúdo principal ── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="border-b border-border bg-card px-6 py-4">
          <div className="flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
                <FileText className="w-6 h-6 text-primary" /> Gerenciar Documentos
              </h1>
              <p className="text-muted-foreground text-sm mt-0.5">
                Habilitação, certidões e documentos da empresa para licitações.
              </p>
            </div>
            <button
              onClick={() => setShowUpload(true)}
              className="flex items-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity flex-shrink-0"
            >
              <Plus className="w-4 h-4" /> Adicionar documento
            </button>
          </div>

          {/* Notas legais */}
          <div className="mt-3 space-y-0.5 text-[11px] text-muted-foreground">
            <p>* Documentos sem data de validade são revisados a cada <strong>90 dias</strong>. Verifique o edital para prazos menores.</p>
            <p>** Para participação via Filial, inclua documentos da Matriz, especialmente fiscais e trabalhistas.</p>
          </div>
        </div>

        {/* Toolbar */}
        <div className="px-6 py-3 border-b border-border flex items-center gap-3 flex-wrap">
          <span className="text-sm text-muted-foreground">
            Listando <strong>{total}</strong> documento(s)
          </span>

          {/* Mobile search */}
          <div className="lg:hidden relative flex-1 min-w-0">
            <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-muted-foreground" />
            <input
              className="w-full pl-8 pr-3 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="Buscar..."
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>

          {/* Download selecionados — always right-aligned */}
          <div className="ml-auto flex items-center gap-2">
            {selected.size > 0 && (
              <span className="text-xs text-muted-foreground">{selected.size} selecionado(s)</span>
            )}
            <button
              onClick={downloadSelected}
              disabled={selectedWithUrl === 0}
              title={selectedWithUrl === 0 ? "Selecione documentos com arquivo para baixar" : `Baixar ${selectedWithUrl} arquivo(s)`}
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-muted transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Download className="w-4 h-4" />
              Download{selectedWithUrl > 0 ? ` (${selectedWithUrl})` : ""}
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="flex-1 overflow-auto px-6 py-4">
          {isLoading ? (
            <div className="space-y-2">
              {[1, 2, 3, 4, 5].map(i => (
                <div key={i} className="h-14 bg-muted animate-pulse rounded-lg" />
              ))}
            </div>
          ) : docs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <FileText className="w-14 h-14 text-muted-foreground opacity-20 mb-4" />
              <h3 className="text-lg font-semibold">Nenhum documento encontrado</h3>
              <p className="text-muted-foreground text-sm mt-1 mb-6">
                {hasFilters ? "Limpe os filtros ou adicione um documento." : "Comece enviando seus documentos de habilitação."}
              </p>
              <button
                onClick={() => setShowUpload(true)}
                className="flex items-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
              >
                <Plus className="w-4 h-4" /> Adicionar documento
              </button>
            </div>
          ) : (
            <div className="bg-card border border-border rounded-xl overflow-hidden shadow-sm">
              {/* Table header */}
              <div className="hidden md:grid grid-cols-[auto_1fr_auto_auto_auto_auto_auto] items-center gap-4 px-4 py-3 bg-muted/50 border-b border-border text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                {/* Select-all checkbox */}
                <input
                  type="checkbox"
                  className="accent-primary w-4 h-4"
                  checked={allSelected}
                  ref={el => { if (el) el.indeterminate = someSelected; }}
                  onChange={toggleSelectAll}
                  title="Selecionar todos"
                />
                <div>Documento</div>
                <div className="text-center w-16">Tipo</div>
                <div className="w-48">Grupo</div>
                <div className="text-center w-24">Situação</div>
                <div className="text-center w-28">Vencimento</div>
                <div className="text-center w-16">Ações</div>
              </div>

              <div className="divide-y divide-border">
                {docs.map((doc) => {
                  const sit = SITUACAO_CONFIG[doc.situacao] ?? SITUACAO_CONFIG.pendente;
                  const SitIcon = sit.icon;
                  const vencendo = isVencendo(doc.dataVencimento);
                  const vencido = isVencido(doc.dataVencimento);
                  const isSelected = selected.has(doc.id);

                  return (
                    <div
                      key={doc.id}
                      className={`grid grid-cols-1 md:grid-cols-[auto_1fr_auto_auto_auto_auto_auto] items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-muted/30 transition-colors ${isSelected ? "bg-primary/5" : ""}`}
                    >
                      {/* Row checkbox */}
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelect(doc.id)}
                        className="accent-primary w-4 h-4 hidden md:block"
                      />

                      {/* Nome */}
                      <div className="min-w-0">
                        <p className="font-medium text-sm truncate" title={doc.nome}>{doc.nome}</p>
                        {doc.descricao && (
                          <p className="text-xs text-muted-foreground truncate">{doc.descricao}</p>
                        )}
                      </div>

                      {/* Tipo */}
                      <div className="flex justify-center w-16">
                        <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${doc.tipoAtualizacao === "auto" ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" : "bg-muted text-muted-foreground"}`}>
                          {doc.tipoAtualizacao === "auto" ? "Auto" : "Manual"}
                        </span>
                      </div>

                      {/* Grupo */}
                      <div className="w-48">
                        <span className="text-xs text-muted-foreground line-clamp-2">{doc.grupo}</span>
                      </div>

                      {/* Situação */}
                      <div className="flex justify-center w-24">
                        <span className={`flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-semibold ${sit.color}`}>
                          <SitIcon className="w-3 h-3" />
                          {sit.label}
                        </span>
                      </div>

                      {/* Vencimento */}
                      <div className="flex justify-center w-28">
                        <span className={`text-xs font-medium ${vencido ? "text-red-600" : vencendo ? "text-amber-600" : "text-muted-foreground"}`}>
                          {vencido && "⚠ "}
                          {vencendo && !vencido && "⏰ "}
                          {formatDate(doc.dataVencimento)}
                        </span>
                      </div>

                      {/* Ações: olho + lixo (sempre visíveis) */}
                      <div className="flex items-center justify-center gap-1 w-16">
                        <a
                          href={doc.url ? `${BASE}${doc.url}` : undefined}
                          target="_blank"
                          rel="noreferrer"
                          onClick={!doc.url ? (e) => e.preventDefault() : undefined}
                          className={`p-1.5 rounded transition-colors ${doc.url ? "hover:bg-primary/10 text-muted-foreground hover:text-primary cursor-pointer" : "text-muted-foreground/30 cursor-not-allowed"}`}
                          title={doc.url ? "Visualizar documento em nova guia" : "Sem arquivo"}
                        >
                          <Eye className="w-4 h-4" />
                        </a>
                        <button
                          onClick={() => setConfirmDelete(doc.id)}
                          className="p-1.5 rounded hover:bg-red-500/10 text-muted-foreground hover:text-red-600 transition-colors"
                          title="Remover"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Upload Dialog ── */}
      {showUpload && <UploadDialog onClose={() => setShowUpload(false)} />}

      {/* ── Confirm Delete ── */}
      {confirmDelete !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={() => setConfirmDelete(null)} />
          <div className="relative bg-card border border-border rounded-xl shadow-2xl p-6 max-w-sm w-full mx-4 space-y-4">
            <h3 className="font-semibold text-lg">Remover documento?</h3>
            <p className="text-sm text-muted-foreground">O arquivo será excluído permanentemente e não poderá ser recuperado.</p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setConfirmDelete(null)} className="px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-muted transition-colors">
                Cancelar
              </button>
              <button
                onClick={() => deleteMut.mutate(confirmDelete!)}
                disabled={deleteMut.isPending}
                className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:opacity-90 disabled:opacity-60 transition-opacity"
              >
                {deleteMut.isPending ? "Removendo..." : "Remover"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
