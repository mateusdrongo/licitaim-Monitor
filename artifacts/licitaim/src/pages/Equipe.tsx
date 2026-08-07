import React from "react";
import { useGetEquipe } from "@workspace/api-client-react";
import { Users, Shield, ShieldAlert, User, MailPlus } from "lucide-react";

export default function Equipe() {
  const { data: equipe, isLoading } = useGetEquipe();

  const getRoleBadge = (role: string) => {
    switch (role) {
      case 'admin': return <span className="flex items-center gap-1 text-xs font-semibold text-destructive bg-destructive/10 px-2 py-1 rounded"><ShieldAlert className="w-3 h-3" /> Admin</span>;
      case 'editor': return <span className="flex items-center gap-1 text-xs font-semibold text-primary bg-primary/10 px-2 py-1 rounded"><Shield className="w-3 h-3" /> Editor</span>;
      default: return <span className="flex items-center gap-1 text-xs font-semibold text-muted-foreground bg-muted px-2 py-1 rounded"><User className="w-3 h-3" /> Visualizador</span>;
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <Users className="w-8 h-8 text-primary" /> Equipe
          </h1>
          <p className="text-muted-foreground mt-1">Gerencie os acessos ao seu ambiente de inteligência.</p>
        </div>
        <button className="bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 rounded-md font-medium flex items-center gap-2 transition-colors">
          <MailPlus className="w-4 h-4" /> Convidar Membro
        </button>
      </div>

      <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-4 space-y-4">
            {[1, 2].map(i => <div key={i} className="h-16 bg-muted animate-pulse rounded" />)}
          </div>
        ) : equipe && equipe.length > 0 ? (
          <table className="w-full text-sm text-left">
            <thead className="bg-muted/50 text-muted-foreground font-medium border-b border-border">
              <tr>
                <th className="px-6 py-4">Usuário</th>
                <th className="px-6 py-4">Papel</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {equipe.map(membro => (
                <tr key={membro.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold">
                        {membro.nome.charAt(0)}
                      </div>
                      <div>
                        <div className="font-medium text-foreground">{membro.nome}</div>
                        <div className="text-xs text-muted-foreground">{membro.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    {getRoleBadge(membro.papel)}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${membro.status === 'ativo' ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400' : 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'}`}>
                      {membro.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button className="text-sm font-medium text-primary hover:underline">Editar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>
    </div>
  );
}
