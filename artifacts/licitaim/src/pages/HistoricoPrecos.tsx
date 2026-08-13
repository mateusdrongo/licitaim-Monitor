import React, { useState } from "react";
import { useGetHistoricoPrecos } from "@workspace/api-client-react";
import {
  LineChart as LChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import {
  LineChart, Search, Building2, MapPin,
  Calendar, TrendingDown, TrendingUp, BarChart3,
  ChevronLeft, ChevronRight,
} from "lucide-react";
import { Link } from "wouter";

const UFS = [
  "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
  "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO",
];

const SITUACAO_LABEL: Record<string, { label: string; cls: string }> = {
  aberta:       { label: "Aberta",       cls: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" },
  em_andamento: { label: "Em andamento", cls: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400" },
  encerrada:    { label: "Encerrada",    cls: "bg-muted text-muted-foreground" },
  cancelada:    { label: "Cancelada",    cls: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" },
  suspensa:     { label: "Suspensa",     cls: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" },
};

const fmt = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

const fmtDate = (d: string | null | undefined) => {
  if (!d) return "—";
  try { return new Date(d).toLocaleDateString("pt-BR"); } catch { return d; }
};

export default function HistoricoPrecos() {
  const [searchTerm, setSearchTerm] = useState("");
  const [uf, setUf] = useState("");
  const [tipo, setTipo] = useState<"estimado" | "homologado">("estimado");
  const [pagina, setPagina] = useState(1);

  // submitted state drives the query
  const [submitted, setSubmitted] = useState<{
    q: string; uf: string; tipo: string; pagina: number;
  } | null>(null);

  const { data, isLoading } = useGetHistoricoPrecos(
    submitted ? { q: submitted.q, uf: submitted.uf || undefined, tipo: submitted.tipo, pagina: submitted.pagina } : { q: "__never__" },
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    { query: { enabled: !!submitted } } as any,
  );

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchTerm.trim()) return;
    const next = { q: searchTerm.trim(), uf, tipo, pagina: 1 };
    setPagina(1);
    setSubmitted(next);
  };

  const changePage = (p: number) => {
    if (!submitted) return;
    setPagina(p);
    setSubmitted({ ...submitted, pagina: p });
  };

  const registros = data?.registros ?? [];
  const hasData   = registros.length > 0;

  // Build chart data: sort by date, deduplicate by month (take mean per month)
  const chartData = (() => {
    const byMonth: Record<string, number[]> = {};
    registros.forEach((r) => {
      if (!r.data) return;
      const month = r.data.slice(0, 7); // YYYY-MM
      (byMonth[month] = byMonth[month] || []).push(r.preco);
    });
    return Object.entries(byMonth)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([month, vals]) => ({
        data:  month + "-15",
        preco: Math.round(vals.reduce((s, v) => s + v, 0) / vals.length),
      }));
  })();

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <LineChart className="w-6 h-6 text-primary" /> Pesquisa de Preços
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Consulte preços estimados e homologados de licitações públicas para balizar sua proposta.
        </p>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="bg-card border border-border rounded-xl p-4 space-y-3">
        <div className="flex gap-3 flex-wrap">
          {/* text */}
          <div className="relative flex-1 min-w-[220px]">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Descreva o item (ex: Notebook, Cadeira, Papel A4)…"
              className="w-full pl-9 pr-3 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          {/* UF */}
          <select
            className="border border-input bg-background rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            value={uf}
            onChange={(e) => setUf(e.target.value)}
          >
            <option value="">Todos os estados</option>
            {UFS.map((u) => <option key={u} value={u}>{u}</option>)}
          </select>

          {/* Tipo toggle */}
          <div className="flex border border-input rounded-lg overflow-hidden text-sm">
            {(["estimado", "homologado"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTipo(t)}
                className={`px-4 py-2 capitalize transition-colors ${
                  tipo === t
                    ? "bg-primary text-primary-foreground"
                    : "bg-background text-foreground hover:bg-muted"
                }`}
              >
                {t === "estimado" ? "Estimado" : "Homologado"}
              </button>
            ))}
          </div>

          <button
            type="submit"
            disabled={!searchTerm.trim() || isLoading}
            className="bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 px-5 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            Buscar
          </button>
        </div>

        <p className="text-xs text-muted-foreground">
          <strong>Estimado:</strong> valor de referência da licitação.&nbsp;
          <strong>Homologado:</strong> valor de licitações encerradas (adjudicadas).
        </p>
      </form>

      {/* Loading */}
      {isLoading && (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 bg-muted animate-pulse rounded-xl" />
          ))}
        </div>
      )}

      {/* No results */}
      {!isLoading && submitted && !hasData && (
        <div className="bg-card border border-border rounded-xl p-12 text-center space-y-2">
          <BarChart3 className="w-10 h-10 text-muted-foreground mx-auto" />
          <p className="font-medium">Nenhum registro encontrado</p>
          <p className="text-sm text-muted-foreground">
            Tente uma descrição mais genérica ou remova o filtro de estado.
            {tipo === "homologado" && " Para homologados, pode não haver registros encerrados com esse termo."}
          </p>
        </div>
      )}

      {/* Initial empty state */}
      {!isLoading && !submitted && (
        <div className="bg-card border border-border rounded-xl p-12 text-center space-y-2">
          <Search className="w-10 h-10 text-muted-foreground mx-auto" />
          <p className="font-medium text-muted-foreground">
            Digite um item acima para consultar preços de licitações públicas
          </p>
        </div>
      )}

      {/* Results */}
      {!isLoading && hasData && (
        <div className="space-y-6">
          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-card border border-border rounded-xl p-5">
              <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Registros</div>
              <div className="text-2xl font-bold font-mono">{data!.totalRegistros.toLocaleString("pt-BR")}</div>
            </div>
            <div className="bg-card border border-border rounded-xl p-5">
              <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Preço Médio</div>
              <div className="text-2xl font-bold font-mono">{fmt(data!.precoMedio)}</div>
            </div>
            <div className="bg-card border border-border rounded-xl p-5">
              <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1 flex items-center gap-1">
                <TrendingDown className="w-3 h-3 text-emerald-500" /> Mínimo
              </div>
              <div className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400">{fmt(data!.precoMinimo)}</div>
            </div>
            <div className="bg-card border border-border rounded-xl p-5">
              <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1 flex items-center gap-1">
                <TrendingUp className="w-3 h-3 text-destructive" /> Máximo
              </div>
              <div className="text-2xl font-bold font-mono text-destructive">{fmt(data!.precoMaximo)}</div>
            </div>
          </div>

          {/* Chart */}
          {chartData.length > 1 && (
            <div className="bg-card border border-border rounded-xl p-6">
              <h3 className="text-sm font-semibold mb-4">
                Tendência — <span className="text-muted-foreground font-normal">{submitted?.q}</span>
              </h3>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <LChart data={chartData} margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis
                      dataKey="data"
                      tickFormatter={(v) => new Date(v).toLocaleDateString("pt-BR", { month: "short", year: "2-digit" })}
                      stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false}
                    />
                    <YAxis
                      tickFormatter={(v) => `R$\u00a0${(v as number).toLocaleString("pt-BR")}`}
                      stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} width={80}
                    />
                    <Tooltip
                      contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", borderRadius: "8px", fontSize: 12 }}
                      formatter={(v: number) => [fmt(v), "Média do mês"]}
                      labelFormatter={(l) => new Date(l).toLocaleDateString("pt-BR", { month: "long", year: "numeric" })}
                    />
                    <Line
                      type="monotone" dataKey="preco"
                      stroke="hsl(var(--primary))" strokeWidth={2}
                      dot={{ r: 3, fill: "hsl(var(--primary))", strokeWidth: 0 }}
                      activeDot={{ r: 5 }}
                    />
                  </LChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Table */}
          <div className="bg-card border border-border rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-border flex items-center justify-between">
              <span className="text-sm font-medium">
                Licitações encontradas
                <span className="ml-2 text-xs text-muted-foreground font-normal">
                  (mostrando até 200 por página — {data!.tipo === "homologado" ? "encerradas" : "todas"})
                </span>
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/40">
                  <tr>
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Objeto</th>
                    <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Valor Est.</th>
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide hidden md:table-cell">Órgão</th>
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide hidden sm:table-cell">UF</th>
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide hidden lg:table-cell">Data</th>
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide hidden xl:table-cell">Modalidade</th>
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Situação</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {registros.map((r, i) => {
                    const sit = SITUACAO_LABEL[r.situacao ?? ""] ?? { label: r.situacao ?? "—", cls: "bg-muted text-muted-foreground" };
                    return (
                      <tr key={i} className="hover:bg-muted/30 transition-colors">
                        <td className="px-4 py-3 max-w-[260px]">
                          <Link
                            href={`/licitacoes/${encodeURIComponent(r.licitacaoId)}`}
                            className="text-primary hover:underline line-clamp-2 leading-snug text-xs"
                          >
                            {r.objeto || r.licitacaoId}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-right font-mono font-semibold whitespace-nowrap">
                          {fmt(r.preco)}
                        </td>
                        <td className="px-4 py-3 hidden md:table-cell max-w-[200px]">
                          <span className="flex items-center gap-1 text-xs text-muted-foreground truncate">
                            <Building2 className="w-3 h-3 shrink-0" />
                            {r.orgao || "—"}
                          </span>
                        </td>
                        <td className="px-4 py-3 hidden sm:table-cell">
                          <span className="flex items-center gap-1 text-xs">
                            <MapPin className="w-3 h-3 text-muted-foreground shrink-0" />
                            {r.uf || "—"}
                          </span>
                        </td>
                        <td className="px-4 py-3 hidden lg:table-cell whitespace-nowrap">
                          <span className="flex items-center gap-1 text-xs text-muted-foreground">
                            <Calendar className="w-3 h-3 shrink-0" />
                            {fmtDate(r.data)}
                          </span>
                        </td>
                        <td className="px-4 py-3 hidden xl:table-cell text-xs text-muted-foreground">
                          {r.modalidade || "—"}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${sit.cls}`}>
                            {sit.label}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {data!.totalPaginas > 1 && (
              <div className="px-5 py-3 border-t border-border flex items-center justify-between text-sm">
                <span className="text-xs text-muted-foreground">
                  Página {data!.pagina} de {data!.totalPaginas}
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => changePage(pagina - 1)}
                    disabled={pagina <= 1}
                    className="p-1.5 rounded border border-border hover:bg-muted disabled:opacity-40 transition-colors"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => changePage(pagina + 1)}
                    disabled={pagina >= data!.totalPaginas}
                    className="p-1.5 rounded border border-border hover:bg-muted disabled:opacity-40 transition-colors"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
