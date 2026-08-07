import React, { useState } from "react";
import { fmtTimeBRT } from "../lib/dateUtils";
import {
  useListMonitoramentos,
  useToggleMonitoramento,
  useDeleteMonitoramento,
  useCreateMonitoramento,
  getListMonitoramentosQueryKey,
} from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Target, Plus, Activity, Power, Trash2, Clock, AlertCircle,
  X, Bot, Tag, MapPin, DollarSign, Layers,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";

// ── tipos locais ──────────────────────────────────────────────────────────────
interface NovoRoboForm {
  nome: string;
  palavrasChaveRaw: string;  // comma-separated input
  modalidades: string[];
  ufs: string[];
  valorMin: string;
  valorMax: string;
}

const MODALIDADES_OPTS = [
  "Pregão Eletrônico",
  "Concorrência",
  "Dispensa de Licitação",
  "Inexigibilidade",
  "Credenciamento",
  "Leilão",
  "RDC",
  "Diálogo Competitivo",
];

const UFS_OPTS = [
  "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
  "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO",
];

const EMPTY_FORM: NovoRoboForm = {
  nome: "",
  palavrasChaveRaw: "",
  modalidades: [],
  ufs: [],
  valorMin: "",
  valorMax: "",
};

// ── Modal de criação ──────────────────────────────────────────────────────────
function NovoRoboDialog({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const { toast } = useToast();
  const createMon = useCreateMonitoramento();
  const [form, setForm] = useState<NovoRoboForm>(EMPTY_FORM);

  if (!open) return null;

  const toggleMulti = (
    key: "modalidades" | "ufs",
    value: string,
  ) => {
    setForm((prev) => ({
      ...prev,
      [key]: prev[key].includes(value)
        ? prev[key].filter((v) => v !== value)
        : [...prev[key], value],
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const nome = form.nome.trim();
    if (!nome) {
      toast({ title: "Nome obrigatório", variant: "destructive" });
      return;
    }

    const palavrasChave = form.palavrasChaveRaw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    createMon.mutate(
      {
        data: {
          nome,
          palavrasChave,
          modalidades: form.modalidades,
          ufs: form.ufs,
          valorMin: form.valorMin ? Number(form.valorMin) : undefined,
          valorMax: form.valorMax ? Number(form.valorMax) : undefined,
          esferas: [],
        },
      },
      {
        onSuccess: () => {
          toast({ title: "Robô criado!", description: `"${nome}" está ativo e varrendo.` });
          setForm(EMPTY_FORM);
          onSuccess();
          onClose();
        },
        onError: () => {
          toast({ title: "Erro ao criar monitoramento", variant: "destructive" });
        },
      },
    );
  };

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-xl">
              <Bot className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h2 className="text-xl font-bold">Novo Robô de Monitoramento</h2>
              <p className="text-sm text-muted-foreground">
                Configure as regras de varredura automática.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-muted transition-colors text-muted-foreground"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto">
          <div className="p-6 space-y-6">
            {/* Nome */}
            <div className="space-y-2">
              <label className="text-sm font-semibold flex items-center gap-2">
                <Bot className="w-4 h-4 text-muted-foreground" />
                Nome do Robô <span className="text-destructive">*</span>
              </label>
              <input
                type="text"
                className="w-full px-4 py-2.5 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                placeholder="Ex: Equipamentos de TI — Federal"
                value={form.nome}
                onChange={(e) => setForm((p) => ({ ...p, nome: e.target.value }))}
              />
            </div>

            {/* Palavras-chave */}
            <div className="space-y-2">
              <label className="text-sm font-semibold flex items-center gap-2">
                <Tag className="w-4 h-4 text-muted-foreground" />
                Palavras-chave
              </label>
              <input
                type="text"
                className="w-full px-4 py-2.5 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                placeholder="notebook, tablet, servidor (separadas por vírgula)"
                value={form.palavrasChaveRaw}
                onChange={(e) =>
                  setForm((p) => ({ ...p, palavrasChaveRaw: e.target.value }))
                }
              />
              {form.palavrasChaveRaw && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {form.palavrasChaveRaw
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean)
                    .map((kw, i) => (
                      <span
                        key={i}
                        className="bg-primary/10 text-primary px-2 py-0.5 rounded text-xs font-medium"
                      >
                        {kw}
                      </span>
                    ))}
                </div>
              )}
            </div>

            {/* Modalidades */}
            <div className="space-y-2">
              <label className="text-sm font-semibold flex items-center gap-2">
                <Layers className="w-4 h-4 text-muted-foreground" />
                Modalidades
                <span className="text-xs text-muted-foreground font-normal">(opcional — deixe vazio para todas)</span>
              </label>
              <div className="flex flex-wrap gap-2">
                {MODALIDADES_OPTS.map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => toggleMulti("modalidades", m)}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                      form.modalidades.includes(m)
                        ? "bg-primary text-primary-foreground border-primary"
                        : "border-border hover:bg-muted"
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>

            {/* UFs */}
            <div className="space-y-2">
              <label className="text-sm font-semibold flex items-center gap-2">
                <MapPin className="w-4 h-4 text-muted-foreground" />
                Estados (UF)
                <span className="text-xs text-muted-foreground font-normal">(opcional — deixe vazio para todo o Brasil)</span>
              </label>
              <div className="flex flex-wrap gap-2">
                {UFS_OPTS.map((uf) => (
                  <button
                    key={uf}
                    type="button"
                    onClick={() => toggleMulti("ufs", uf)}
                    className={`w-10 py-1.5 rounded text-xs font-mono font-bold border transition-colors ${
                      form.ufs.includes(uf)
                        ? "bg-primary text-primary-foreground border-primary"
                        : "border-border hover:bg-muted"
                    }`}
                  >
                    {uf}
                  </button>
                ))}
              </div>
            </div>

            {/* Valor */}
            <div className="space-y-2">
              <label className="text-sm font-semibold flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-muted-foreground" />
                Faixa de Valor (R$)
                <span className="text-xs text-muted-foreground font-normal">(opcional)</span>
              </label>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Mínimo</label>
                  <input
                    type="number"
                    min="0"
                    step="1000"
                    className="w-full px-3 py-2 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary transition-all text-sm"
                    placeholder="500000"
                    value={form.valorMin}
                    onChange={(e) => setForm((p) => ({ ...p, valorMin: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Máximo</label>
                  <input
                    type="number"
                    min="0"
                    step="1000"
                    className="w-full px-3 py-2 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary transition-all text-sm"
                    placeholder="10000000"
                    value={form.valorMax}
                    onChange={(e) => setForm((p) => ({ ...p, valorMax: e.target.value }))}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="p-6 border-t border-border bg-muted/20 flex justify-end gap-3 shrink-0">
            <button
              type="button"
              onClick={onClose}
              className="px-5 py-2.5 rounded-lg border border-border font-medium hover:bg-muted transition-colors text-sm"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={createMon.isPending || !form.nome.trim()}
              className="px-5 py-2.5 rounded-lg bg-primary text-primary-foreground font-semibold hover:bg-primary/90 disabled:opacity-50 transition-colors text-sm flex items-center gap-2"
            >
              {createMon.isPending ? (
                <>
                  <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                  Criando...
                </>
              ) : (
                <>
                  <Bot className="w-4 h-4" />
                  Criar Robô
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Página principal ──────────────────────────────────────────────────────────
export default function Monitoramentos() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [dialogOpen, setDialogOpen] = useState(false);

  const { data: monitoramentos, isLoading } = useListMonitoramentos();
  const toggleStatus = useToggleMonitoramento();
  const deleteMon   = useDeleteMonitoramento();

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: getListMonitoramentosQueryKey() });

  const handleToggle = (id: number) => {
    toggleStatus.mutate(
      { id },
      {
        onSuccess: () => {
          toast({ title: "Status alterado", description: "Monitoramento atualizado." });
          invalidate();
        },
      },
    );
  };

  const handleDelete = (id: number) => {
    if (!confirm("Tem certeza que deseja remover este monitoramento?")) return;
    deleteMon.mutate(
      { id },
      {
        onSuccess: () => {
          toast({ title: "Removido", description: "Monitoramento excluído com sucesso." });
          invalidate();
        },
      },
    );
  };

  return (
    <>
      <NovoRoboDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSuccess={invalidate}
      />

      <div className="p-8 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
              <Target className="w-8 h-8 text-primary" />
              Monitoramentos Ativos
            </h1>
            <p className="text-muted-foreground mt-1">
              Robôs varrendo diários oficiais e PNCP com suas regras.
            </p>
          </div>
          <button
            onClick={() => setDialogOpen(true)}
            className="bg-primary text-primary-foreground hover:bg-primary/90 px-5 py-2.5 rounded-lg font-semibold flex items-center gap-2 transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4" />
            Novo Robô
          </button>
        </div>

        {/* Grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-48 bg-muted animate-pulse rounded-xl" />
            ))}
          </div>
        ) : monitoramentos && monitoramentos.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {monitoramentos.map((mon) => (
              <div
                key={mon.id}
                className="bg-card border border-border rounded-xl shadow-sm overflow-hidden flex flex-col group hover:border-primary/50 transition-colors"
              >
                <div className="p-5 border-b border-border flex justify-between items-start bg-muted/20">
                  <div className="space-y-1 min-w-0 flex-1 mr-2">
                    <h3 className="font-bold text-lg text-foreground truncate">{mon.nome}</h3>
                    <div className="flex items-center gap-2 text-xs font-medium">
                      <span
                        className={`flex items-center gap-1 ${
                          mon.ativo ? "text-emerald-600" : "text-muted-foreground"
                        }`}
                      >
                        <span
                          className={`w-2 h-2 rounded-full ${
                            mon.ativo
                              ? "bg-emerald-500 animate-pulse"
                              : "bg-muted-foreground"
                          }`}
                        />
                        {mon.ativo ? "Em execução" : "Pausado"}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleToggle(mon.id)}
                    className={`p-2 rounded-md transition-colors flex-shrink-0 ${
                      mon.ativo
                        ? "text-primary hover:bg-primary/10"
                        : "text-muted-foreground hover:bg-muted"
                    }`}
                    title={mon.ativo ? "Pausar" : "Ativar"}
                  >
                    <Power className="w-5 h-5" />
                  </button>
                </div>

                <div className="p-5 flex-1 space-y-4">
                  {/* Keywords */}
                  <div>
                    <div className="text-xs text-muted-foreground mb-2 font-medium uppercase tracking-wider">
                      Palavras-chave
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {(mon.palavrasChave ?? []).length > 0 ? (
                        (mon.palavrasChave ?? []).map((kw: string, idx: number) => (
                          <span
                            key={idx}
                            className="bg-primary/10 text-primary px-2 py-0.5 rounded text-xs font-medium"
                          >
                            {kw}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs text-muted-foreground italic">Sem filtro de palavras</span>
                      )}
                    </div>
                  </div>

                  {/* UFs */}
                  {(mon.ufs ?? []).length > 0 && (
                    <div>
                      <div className="text-xs text-muted-foreground mb-1.5 font-medium uppercase tracking-wider">
                        Estados
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {(mon.ufs ?? []).map((uf: string) => (
                          <span
                            key={uf}
                            className="bg-muted text-muted-foreground px-2 py-0.5 rounded text-xs font-mono font-bold"
                          >
                            {uf}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-xs text-muted-foreground mb-1 font-medium uppercase tracking-wider">
                        Alertas Gerados
                      </div>
                      <div className="font-mono text-xl font-bold flex items-center gap-2 text-amber-600">
                        <AlertCircle className="w-4 h-4" />
                        {mon.totalAlertas ?? 0}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground mb-1 font-medium uppercase tracking-wider">
                        Última Varredura
                      </div>
                      <div className="text-sm font-medium flex items-center gap-1.5 mt-1">
                        <Clock className="w-4 h-4 text-muted-foreground" />
                        {mon.ultimaExecucao
                          ? fmtTimeBRT(mon.ultimaExecucao)
                          : "—"}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="p-3 bg-muted/30 border-t border-border flex justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => handleDelete(mon.id)}
                    className="text-xs text-destructive hover:bg-destructive/10 px-2 py-1 rounded transition-colors flex items-center gap-1 font-medium"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Excluir
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-20 bg-card border border-dashed border-border rounded-xl">
            <div className="w-16 h-16 bg-muted rounded-2xl flex items-center justify-center mx-auto mb-4">
              <Activity className="w-8 h-8 text-muted-foreground opacity-40" />
            </div>
            <h3 className="text-lg font-semibold">Nenhum robô ativo</h3>
            <p className="text-muted-foreground mt-1 mb-6">
              Crie seu primeiro robô para automatizar a busca por editais.
            </p>
            <button
              onClick={() => setDialogOpen(true)}
              className="bg-primary text-primary-foreground hover:bg-primary/90 px-5 py-2.5 rounded-lg font-semibold inline-flex items-center gap-2 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Criar primeiro robô
            </button>
          </div>
        )}
      </div>
    </>
  );
}
