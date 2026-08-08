import { WifiOff, X, RefreshCw, Wifi } from "lucide-react";
import { useBackendStatus } from "@/contexts/BackendStatusContext";
import { useQueryClient } from "@tanstack/react-query";

/**
 * Sticky banner shown at the top of the page when the backend is unreachable.
 *
 * States:
 *  - "offline"  → red error banner with manual retry / dismiss buttons
 *  - "restored" → green confirmation banner that auto-disappears after ~2.5s
 *  - "online"   → nothing rendered
 *
 * Rendered inside BackendStatusProvider so it can read the context.
 */
export function NetworkErrorBanner() {
  const { status, dismiss } = useBackendStatus();
  const queryClient = useQueryClient();

  if (status === "online") return null;

  if (status === "restored") {
    return (
      <div
        role="status"
        aria-live="polite"
        className="fixed top-0 inset-x-0 z-[9999] flex items-center justify-center gap-2 bg-green-600 px-4 py-2.5 text-white shadow-md animate-in fade-in slide-in-from-top-2 duration-300"
      >
        <Wifi className="w-4 h-4 shrink-0" />
        <span className="text-sm font-medium">Conexão restaurada</span>
      </div>
    );
  }

  // status === "offline"
  const handleRetry = () => {
    dismiss();
    queryClient.invalidateQueries();
  };

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="fixed top-0 inset-x-0 z-[9999] flex items-center justify-between gap-3 bg-destructive px-4 py-2.5 text-destructive-foreground shadow-md"
    >
      <div className="flex items-center gap-2 text-sm font-medium">
        <WifiOff className="w-4 h-4 shrink-0" />
        <span>
          Não foi possível conectar ao servidor. Verificando automaticamente…
        </span>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={handleRetry}
          className="flex items-center gap-1.5 text-xs font-medium underline-offset-2 hover:underline opacity-90 hover:opacity-100 transition-opacity"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Tentar agora
        </button>
        <button
          onClick={dismiss}
          aria-label="Fechar aviso"
          className="ml-2 opacity-80 hover:opacity-100 transition-opacity"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
