import React from "react";
import { AlertCircle, ServerCrash, RefreshCw, WifiOff } from "lucide-react";

type ErrorKind = "network" | "server" | "unknown";

function classifyError(error: Error | unknown): ErrorKind {
  if (!error) return "unknown";
  const msg = error instanceof Error ? error.message.toLowerCase() : String(error).toLowerCase();
  if (
    msg.includes("failed to fetch") ||
    msg.includes("networkerror") ||
    msg.includes("network error") ||
    msg.includes("load failed") ||
    msg.includes("offline") ||
    msg.includes("net::err")
  ) {
    return "network";
  }
  if (
    msg.includes("500") ||
    msg.includes("502") ||
    msg.includes("503") ||
    msg.includes("server") ||
    msg.includes("internal")
  ) {
    return "server";
  }
  return "unknown";
}

interface PageErrorStateProps {
  /** The error object from the query */
  error?: Error | unknown | null;
  /** Called when the user clicks "Tentar novamente" */
  onRetry?: () => void;
  /** Optional override for the main message */
  message?: string;
  /** Compact inline variant (less vertical padding) */
  compact?: boolean;
}

/**
 * Consistent error state for pages that fail to load their data.
 * Shows the failure type (network vs server) and a retry button.
 */
export function PageErrorState({ error, onRetry, message, compact = false }: PageErrorStateProps) {
  const kind = classifyError(error);

  const icon =
    kind === "network" ? (
      <WifiOff className="w-8 h-8 text-muted-foreground" />
    ) : kind === "server" ? (
      <ServerCrash className="w-8 h-8 text-muted-foreground" />
    ) : (
      <AlertCircle className="w-8 h-8 text-muted-foreground" />
    );

  const title =
    kind === "network"
      ? "Sem conexão com o servidor"
      : kind === "server"
      ? "Erro no servidor"
      : "Erro ao carregar dados";

  const description =
    message ??
    (kind === "network"
      ? "Verifique sua conexão ou aguarde o servidor voltar ao ar."
      : kind === "server"
      ? "O servidor retornou um erro inesperado. Tente novamente em instantes."
      : "Não foi possível carregar os dados desta página.");

  return (
    <div
      className={`flex flex-col items-center justify-center text-center gap-4 ${
        compact ? "py-12 px-4" : "py-24 px-6"
      }`}
    >
      <div className="p-3 rounded-full bg-muted">{icon}</div>
      <div>
        <p className="font-semibold text-foreground mb-1">{title}</p>
        <p className="text-sm text-muted-foreground max-w-sm">{description}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Tentar novamente
        </button>
      )}
    </div>
  );
}
