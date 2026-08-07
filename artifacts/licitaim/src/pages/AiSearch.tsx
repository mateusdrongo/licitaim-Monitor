import React, { useState } from "react";
import { useAiSearch } from "@workspace/api-client-react";
import { BrainCircuit, Search, Sparkles, Building2, MapPin } from "lucide-react";
import { Link } from "wouter";

export default function AiSearch() {
  const [query, setQuery] = useState("");
  const doSearch = useAiSearch();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    doSearch.mutate({ data: { query } });
  };

  const { data, isPending, isSuccess } = doSearch;

  const formatCurrency = (value: number | null | undefined) => {
    if (value == null) return "Não estimado";
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8 h-[calc(100vh-2rem)] flex flex-col">
      <div className="text-center space-y-4 pt-12 shrink-0">
        <div className="w-16 h-16 bg-primary/10 rounded-2xl flex items-center justify-center mx-auto shadow-inner">
          <BrainCircuit className="w-8 h-8 text-primary" />
        </div>
        <h1 className="text-4xl font-bold tracking-tight text-foreground">Inteligência LicitAIM</h1>
        <p className="text-muted-foreground max-w-2xl mx-auto">
          Busca semântica avançada. Descreva o que você procura em linguagem natural e nós interpretamos regras, modalidades e escopos.
        </p>
      </div>

      <form onSubmit={handleSearch} className="shrink-0 relative group max-w-3xl mx-auto w-full z-10">
        <div className="absolute inset-0 bg-primary/20 rounded-2xl blur-xl transition-all duration-500 group-hover:bg-primary/30" />
        <div className="relative bg-card border-2 border-primary/20 rounded-2xl shadow-xl flex overflow-hidden group-focus-within:border-primary/50 transition-colors">
          <input 
            type="text"
            className="flex-1 bg-transparent px-6 py-4 text-lg outline-none placeholder:text-muted-foreground/70"
            placeholder="Ex: 'Licitações de TI no estado de SP acima de 1 milhão que ainda estão abertas'"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button 
            type="submit" 
            disabled={isPending || !query}
            className="bg-primary hover:bg-primary/90 text-primary-foreground px-8 font-medium transition-colors flex items-center gap-2 disabled:opacity-50"
          >
            {isPending ? (
              <span className="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : (
              <><Sparkles className="w-5 h-5" /> Encontrar</>
            )}
          </button>
        </div>
      </form>

      <div className="flex-1 overflow-y-auto min-h-0 relative -mx-8 px-8">
        {isSuccess && data && (
          <div className="max-w-3xl mx-auto space-y-6 pb-12 animate-in fade-in slide-in-from-bottom-8 duration-700">
            {/* AI Interpretation block */}
            <div className="bg-primary/5 border border-primary/20 rounded-xl p-5 shadow-sm">
              <div className="flex items-start gap-3">
                <BrainCircuit className="w-5 h-5 text-primary shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-sm font-bold text-foreground">Interpretação da IA:</h4>
                  <p className="text-sm text-muted-foreground mt-1 leading-relaxed">
                    {data.interpretacao}
                  </p>
                  
                  {data.filtrosGerados && (
                    <div className="flex flex-wrap gap-2 mt-3">
                      {data.filtrosGerados.modalidades?.map(m => (
                        <span key={m} className="px-2 py-1 bg-background border border-border rounded text-xs font-mono">{m}</span>
                      ))}
                      {data.filtrosGerados.ufs?.map(uf => (
                        <span key={uf} className="px-2 py-1 bg-background border border-border rounded text-xs font-mono">{uf}</span>
                      ))}
                      {data.filtrosGerados.valorMin && (
                        <span className="px-2 py-1 bg-background border border-border rounded text-xs font-mono">Min: R$ {data.filtrosGerados.valorMin}</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <h3 className="text-lg font-bold pt-4 border-b border-border pb-2">
              {data.resultados.length} resultados encontrados para esta intenção
            </h3>

            <div className="space-y-4">
              {data.resultados.map(lic => (
                 <Link 
                  key={lic.id} 
                  href={`/licitacoes/${lic.id}`}
                  className="block bg-card border border-border rounded-xl p-5 shadow-sm hover:border-primary/50 transition-colors group"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="px-2 py-0.5 rounded bg-primary/10 text-primary text-xs font-bold font-mono tracking-tight">
                      {lic.modalidade}
                    </span>
                    <span className="text-xs font-medium text-muted-foreground font-mono">
                      {lic.numero}
                    </span>
                  </div>
                  <h4 className="text-base font-bold text-foreground leading-snug group-hover:text-primary transition-colors">
                    {lic.objeto}
                  </h4>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground mt-3">
                    <span className="flex items-center gap-1.5"><Building2 className="w-3.5 h-3.5" /> {lic.orgaoNome}</span>
                    <span className="flex items-center gap-1.5"><MapPin className="w-3.5 h-3.5" /> {lic.uf}</span>
                    <span className="font-mono text-emerald-600 font-bold ml-auto">{formatCurrency(lic.valorEstimado)}</span>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
