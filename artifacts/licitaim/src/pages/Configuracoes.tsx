import React from "react";
import { useGetMe } from "@workspace/api-client-react";
import { Settings, Building, CreditCard, ShieldCheck } from "lucide-react";

export default function Configuracoes() {
  const { data: user, isLoading } = useGetMe();

  if (isLoading) return <div className="p-8">Carregando...</div>;
  if (!user) return null;

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
          <Settings className="w-8 h-8 text-primary" /> Configurações
        </h1>
        <p className="text-muted-foreground mt-1">Preferências da conta e detalhes da empresa.</p>
      </div>

      <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
        <div className="p-6 border-b border-border flex items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center text-primary text-2xl font-bold">
            {user.nome.charAt(0)}
          </div>
          <div>
            <h2 className="text-xl font-bold text-foreground">{user.nome}</h2>
            <p className="text-muted-foreground">{user.email}</p>
          </div>
        </div>

        <div className="p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <Building className="w-4 h-4" /> Empresa
              </label>
              <div className="p-3 bg-muted rounded-md font-medium">{user.empresa || '-'}</div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <ShieldCheck className="w-4 h-4" /> CNPJ
              </label>
              <div className="p-3 bg-muted rounded-md font-mono">{user.cnpj || '-'}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-gradient-to-br from-primary/10 to-transparent border border-primary/20 rounded-xl p-6 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-32 h-32 bg-primary/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
        <h3 className="text-lg font-bold text-foreground flex items-center gap-2 mb-2">
          <CreditCard className="w-5 h-5 text-primary" /> Plano Atual: <span className="capitalize text-primary">{user.plano}</span>
        </h3>
        <p className="text-sm text-muted-foreground mb-4">
          Sua empresa está utilizando o plano {user.plano} com acesso a todas as funcionalidades de monitoramento e pesquisa com IA.
        </p>
        <button className="bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 rounded-md text-sm font-medium transition-colors">
          Gerenciar Assinatura
        </button>
      </div>
    </div>
  );
}
