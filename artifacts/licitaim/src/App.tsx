import React from "react";
import { Route, Switch, Router as WouterRouter } from "wouter";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ErrorBoundary } from "@/components/ErrorBoundary";

import NotFound from "@/pages/not-found";
import { AppLayout } from "@/components/layout/AppLayout";

// Public pages
import LandingPage from "@/pages/LandingPage";
import Login from "@/pages/Login";
import Cadastro from "@/pages/Cadastro";

// App pages
import Dashboard from "@/pages/Dashboard";
import Licitacoes from "@/pages/Licitacoes";
import LicitacaoDetail from "@/pages/LicitacaoDetail";
import Favoritos from "@/pages/Favoritos";
import Monitoramentos from "@/pages/Monitoramentos";
import Alertas from "@/pages/Alertas";
import Documentos from "@/pages/Documentos";
import Oportunidades from "@/pages/Oportunidades";
import HistoricoPrecos from "@/pages/HistoricoPrecos";
import AiSearch from "@/pages/AiSearch";
import Equipe from "@/pages/Equipe";
import Configuracoes from "@/pages/Configuracoes";
import Agenda from "@/pages/Agenda";
import Certidoes from "@/pages/Certidoes";
import Analytics from "@/pages/Analytics";
import GerenciamentoLista from "@/pages/GerenciamentoLista";
import GerenciamentoDetalhe from "@/pages/GerenciamentoDetalhe";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function AppRoutes() {
  return (
    <Switch>
      {/* Landing page — rota raiz pública */}
      <Route path="/" component={LandingPage} />

      {/* Autenticação */}
      <Route path="/entrar" component={Login} />
      <Route path="/cadastro" component={Cadastro} />

      {/* App autenticado — (.*) casa com qualquer nº de segmentos, ao contrário
           de /:rest* que em modo estrito só casa com um segmento */}
      <Route path="(.*)">
        <AppLayout>
          <ErrorBoundary>
          <Switch>
            <Route path="/dashboard" component={Dashboard} />
            <Route path="/licitacoes" component={Licitacoes} />
            <Route path="/licitacoes/:id" component={LicitacaoDetail} />
            <Route path="/favoritos" component={Favoritos} />
            <Route path="/monitoramentos" component={Monitoramentos} />
            <Route path="/alertas" component={Alertas} />
            <Route path="/documentos" component={Documentos} />
            <Route path="/oportunidades" component={Oportunidades} />
            <Route path="/historico-precos" component={HistoricoPrecos} />
            <Route path="/ai-search" component={AiSearch} />
            <Route path="/equipe" component={Equipe} />
            <Route path="/configuracoes" component={Configuracoes} />
            <Route path="/agenda" component={Agenda} />
            <Route path="/certidoes" component={Certidoes} />
            <Route path="/analytics" component={Analytics} />
            <Route path="/gerenciamento" component={GerenciamentoLista} />
            <Route path="/gerenciamento/:id" component={GerenciamentoDetalhe} />
            <Route component={NotFound} />
          </Switch>
          </ErrorBoundary>
        </AppLayout>
      </Route>
    </Switch>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, "")}>
          <AppRoutes />
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
