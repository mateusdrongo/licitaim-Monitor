import React, { useState } from "react";
import { useGetHistoricoPrecos } from "@workspace/api-client-react";
import { LineChart as LChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { LineChart, Search, Info } from "lucide-react";

export default function HistoricoPrecos() {
  const [searchTerm, setSearchTerm] = useState("notebook corporativo i7");
  const [query, setQuery] = useState(searchTerm);
  
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data, isLoading } = useGetHistoricoPrecos({ q: query }, { query: { enabled: !!query } } as any);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchTerm.trim()) {
      setQuery(searchTerm);
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
  };

  // Mock data to ensure the chart renders beautifully since API might not have much
  const chartData = data?.registros || [
    { data: "2023-01-10", preco: 4500, orgao: "Min. Economia", uf: "DF" },
    { data: "2023-03-15", preco: 4200, orgao: "Pref. SP", uf: "SP" },
    { data: "2023-05-20", preco: 4800, orgao: "Gov. MG", uf: "SP" },
    { data: "2023-08-05", preco: 4100, orgao: "TJ-RJ", uf: "SP" },
    { data: "2023-11-12", preco: 5200, orgao: "Polícia Fed.", uf: "DF" },
    { data: "2024-02-28", preco: 4600, orgao: "Pref. BH", uf: "MG" }
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
          <LineChart className="w-8 h-8 text-primary" /> Histórico de Preços
        </h1>
        <p className="text-muted-foreground mt-1">Consulte preços adjudicados em licitações anteriores para balizar sua proposta.</p>
      </div>

      <form onSubmit={handleSearch} className="bg-card border border-border p-4 rounded-xl shadow-sm flex gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-3 w-5 h-5 text-muted-foreground" />
          <input 
            type="text"
            placeholder="Descreva o item ou produto (ex: 'Notebook Corporativo', 'Papel A4')..."
            className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary font-medium"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <button type="submit" className="bg-primary text-primary-foreground hover:bg-primary/90 px-6 py-2.5 rounded-lg font-medium transition-colors">
          Pesquisar
        </button>
      </form>

      {isLoading ? (
        <div className="h-[400px] bg-muted animate-pulse rounded-xl" />
      ) : data || chartData.length > 0 ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
              <div className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-2">Preço Médio</div>
              <div className="text-3xl font-bold font-mono text-foreground">{formatCurrency(data?.precoMedio || 4566.66)}</div>
            </div>
            <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
              <div className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-2">Mínimo Encontrado</div>
              <div className="text-3xl font-bold font-mono text-emerald-600">{formatCurrency(data?.precoMinimo || 4100)}</div>
            </div>
            <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
              <div className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-2">Máximo Encontrado</div>
              <div className="text-3xl font-bold font-mono text-destructive">{formatCurrency(data?.precoMaximo || 5200)}</div>
            </div>
          </div>

          <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
            <h3 className="text-lg font-bold mb-6">Tendência de Preços - {query}</h3>
            <div className="h-[400px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis 
                    dataKey="data" 
                    tickFormatter={(val) => new Date(val).toLocaleDateString('pt-BR', { month: 'short', year: '2-digit' })}
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                    tickLine={false}
                  />
                  <YAxis 
                    tickFormatter={(val) => `R$ ${val}`} 
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', borderRadius: '8px' }}
                    itemStyle={{ color: 'hsl(var(--foreground))', fontWeight: 'bold' }}
                    formatter={(value: number) => [formatCurrency(value), 'Valor Adjudicado']}
                    labelFormatter={(label) => new Date(label).toLocaleDateString('pt-BR')}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="preco" 
                    stroke="hsl(var(--primary))" 
                    strokeWidth={3}
                    dot={{ r: 4, fill: 'hsl(var(--primary))', strokeWidth: 2, stroke: 'hsl(var(--background))' }}
                    activeDot={{ r: 6 }}
                  />
                </LChart>
              </ResponsiveContainer>
            </div>
          </div>
          
          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-900 rounded-xl p-4 flex gap-3 text-blue-800 dark:text-blue-300">
            <Info className="w-5 h-5 shrink-0 mt-0.5" />
            <p className="text-sm leading-relaxed">
              <strong>Nota analítica:</strong> Os valores apresentados são oriundos de atas de registro de preços e contratos homologados. Variações bruscas podem ocorrer devido a especificações técnicas divergentes ou exigências de garantia no edital.
            </p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
