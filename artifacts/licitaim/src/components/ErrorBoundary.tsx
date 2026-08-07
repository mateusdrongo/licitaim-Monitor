import React from "react";
import { AlertTriangle, RotateCcw, ArrowLeft } from "lucide-react";

interface Props {
  children: React.ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Global ErrorBoundary — wraps all authenticated routes so any uncaught
 * React render exception shows a friendly message instead of a blank page.
 */
export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  reset = () => this.setState({ error: null });

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-5 px-6 text-center">
          <div className="p-4 bg-destructive/10 rounded-full">
            <AlertTriangle className="w-10 h-10 text-destructive" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground mb-1">
              Algo deu errado
            </h2>
            <p className="text-sm text-muted-foreground max-w-sm">
              Ocorreu um erro inesperado nesta página. Você pode tentar novamente
              ou voltar à página anterior.
            </p>
            {import.meta.env.DEV && (
              <pre className="mt-3 text-left text-xs bg-muted rounded-lg p-3 max-w-lg overflow-auto text-destructive">
                {this.state.error.message}
              </pre>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={this.reset}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
              Tentar novamente
            </button>
            <a
              href="/"
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-muted transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Início
            </a>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
