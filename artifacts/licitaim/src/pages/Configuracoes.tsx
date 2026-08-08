import React, { useState, useEffect } from "react";
import { useGetMe, usePatchMe } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Settings, Building, CreditCard, ShieldCheck, Send, Mail, ExternalLink, Check } from "lucide-react";

export default function Configuracoes() {
  const { data: user, isLoading } = useGetMe();
  const queryClient = useQueryClient();
  const patchMe = usePatchMe();

  const [notifEmail, setNotifEmail] = useState(true);
  const [notifTelegram, setNotifTelegram] = useState(false);
  const [telegramChatId, setTelegramChatId] = useState("");
  const [saved, setSaved] = useState(false);

  // Sync state when user data loads
  useEffect(() => {
    if (user) {
      setNotifEmail(user.notifEmail ?? true);
      setNotifTelegram(user.notifTelegram ?? false);
      setTelegramChatId(user.telegramChatId ?? "");
    }
  }, [user]);

  const handleSave = async () => {
    await patchMe.mutateAsync({
      data: {
        notif_email: notifEmail,
        notif_telegram: notifTelegram,
        telegram_chat_id: telegramChatId,
      },
    });
    queryClient.invalidateQueries({ queryKey: ["/api/auth/me"] });
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

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

      {/* Profile card */}
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

      {/* Notification settings card */}
      <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
        <div className="p-6 border-b border-border">
          <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
            <Send className="w-5 h-5 text-primary" /> Configurações de Notificação
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Escolha como deseja receber alertas de licitações favoritas.
          </p>
        </div>

        <div className="p-6 space-y-6">
          {/* Email toggle */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Mail className="w-5 h-5 text-muted-foreground" />
              <div>
                <p className="font-medium text-foreground">E-mail</p>
                <p className="text-sm text-muted-foreground">Receber alertas no e-mail da conta</p>
              </div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={notifEmail}
              onClick={() => setNotifEmail(!notifEmail)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 ${
                notifEmail ? "bg-primary" : "bg-muted-foreground/30"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${
                  notifEmail ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>

          {/* Telegram toggle */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Send className="w-5 h-5 text-muted-foreground" />
                <div>
                  <p className="font-medium text-foreground">Telegram</p>
                  <p className="text-sm text-muted-foreground">Receber alertas via bot do Telegram</p>
                </div>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={notifTelegram}
                onClick={() => setNotifTelegram(!notifTelegram)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 ${
                  notifTelegram ? "bg-primary" : "bg-muted-foreground/30"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${
                    notifTelegram ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>

            {/* Telegram chat ID input — shown when Telegram is enabled */}
            {notifTelegram && (
              <div className="ml-8 space-y-2 animate-in fade-in slide-in-from-top-1 duration-200">
                <label htmlFor="telegram-chat-id" className="text-sm font-medium text-foreground">
                  Seu Telegram Chat ID
                </label>
                <input
                  id="telegram-chat-id"
                  type="text"
                  value={telegramChatId}
                  onChange={(e) => setTelegramChatId(e.target.value)}
                  placeholder="Ex: 123456789"
                  className="w-full px-3 py-2 rounded-md border border-border bg-background text-foreground text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                />
                <p className="text-xs text-muted-foreground flex items-center gap-1">
                  Não sabe seu Chat ID? Fale com{" "}
                  <a
                    href="https://t.me/userinfobot"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline inline-flex items-center gap-0.5"
                  >
                    @userinfobot <ExternalLink className="w-3 h-3" />
                  </a>{" "}
                  no Telegram — ele te envia o ID na hora.
                </p>
              </div>
            )}
          </div>

          {/* Save button */}
          <div className="flex items-center justify-end gap-3 pt-2 border-t border-border">
            {saved && (
              <span className="text-sm text-green-600 dark:text-green-400 flex items-center gap-1 animate-in fade-in duration-200">
                <Check className="w-4 h-4" /> Preferências salvas
              </span>
            )}
            <button
              onClick={handleSave}
              disabled={patchMe.isPending}
              className="bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 px-4 py-2 rounded-md text-sm font-medium transition-colors"
            >
              {patchMe.isPending ? "Salvando…" : "Salvar preferências"}
            </button>
          </div>
        </div>
      </div>

      {/* Plan card */}
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
