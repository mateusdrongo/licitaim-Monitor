// @vitest-environment jsdom
/**
 * Integration tests: render GerenciamentoDetalhe with mocked apiFetch,
 * trigger the real UI flows (Finalizar → Confirmar for PATCH; Remover for DELETE),
 * and assert that the correct destructive toast fires on 401 and non-401 errors.
 */

// vi.mock is hoisted — factory runs before any import resolves
import { vi } from "vitest";
vi.mock("@/lib/apiFetch", () => ({
  apiFetch: vi.fn(),
  dispatchOfflineEvent: vi.fn(),
  onOfflineEvent: vi.fn(() => () => {}),
  isNetworkError: vi.fn(() => false),
}));

import React, { act } from "react";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Router } from "wouter";

import { apiFetch } from "@/lib/apiFetch";
import { Toaster } from "@/components/ui/toaster";
import { dispatch } from "@/hooks/use-toast";
import GerenciamentoDetalhe from "@/pages/GerenciamentoDetalhe";

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeResponse(status: number, body: unknown = {}): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

/** Minimal GerItem — status em_andamento so the Finalizar button is visible. */
const MOCK_GER = {
  id: 1,
  licitacaoId: "licit-1",
  licitacaoObjeto: "Objeto de teste",
  status: "em_andamento",
  totalTarefas: 0,
  tarefasConcluidas: 0,
  totalAnotacoes: 0,
  criadoEm: "2026-01-01T00:00:00Z",
  atualizadoEm: "2026-01-01T00:00:00Z",
};

/**
 * Install an apiFetch mock that returns patchStatus for PATCH on the root
 * gerenciamento endpoint, deleteStatus for DELETE, and valid fixtures for all
 * GET queries the component fires on mount.
 */
function setupApiFetch(patchStatus: number, deleteStatus: number) {
  vi.mocked(apiFetch).mockImplementation(async (input, init?) => {
    const url = input.toString();
    const method = (init?.method ?? "GET").toUpperCase();

    // Mutation endpoints — checked by method first so the same URL path doesn't
    // accidentally match the GET handler below.
    if (method === "PATCH" && /\/api\/gerenciamento\/\d+$/.test(url)) {
      return makeResponse(patchStatus);
    }
    if (method === "DELETE" && /\/api\/gerenciamento\/\d+$/.test(url)) {
      return makeResponse(deleteStatus);
    }

    // Sub-resource GETs (more specific patterns first)
    if (/\/api\/gerenciamento\/\d+\/tarefas/.test(url)) return makeResponse(200, { data: [] });
    if (/\/api\/gerenciamento\/\d+\/anotacoes/.test(url)) return makeResponse(200, { data: [] });
    if (/\/api\/gerenciamento\/\d+\/habilitacao/.test(url)) return makeResponse(200, { data: [] });
    if (/\/api\/alertas/.test(url)) return makeResponse(200, { data: [] });

    // Main gerenciamento GET
    if (/\/api\/gerenciamento\/\d+$/.test(url)) return makeResponse(200, MOCK_GER);

    return makeResponse(404);
  });
}

/**
 * Render the page inside the required QueryClient + Router providers.
 * window.location.pathname must already contain `/gerenciamento/1` so the
 * component's gerId fallback extraction resolves correctly.
 */
function renderPage() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={qc}>
      <Router>
        <GerenciamentoDetalhe />
        <Toaster />
      </Router>
    </QueryClientProvider>
  );
}

// ── updateGer toast tests ─────────────────────────────────────────────────────

describe("GerenciamentoDetalhe – updateGer onError toast", () => {
  beforeEach(() => {
    // gerId fallback reads window.location via useLocation and window.location.pathname
    window.history.pushState({}, "", "/gerenciamento/1");
  });

  afterEach(async () => {
    vi.clearAllMocks();
    // Unmount all rendered trees so the next test starts with a clean DOM
    cleanup();
    await act(async () => { dispatch({ type: "REMOVE_TOAST" }); });
  });

  it("shows 'Sessão expirada' toast when PATCH /api/gerenciamento/:id returns 401", async () => {
    setupApiFetch(401, 204);
    renderPage();

    // Wait for the page to finish loading — Finalizar is only shown when status === em_andamento
    const finalizarBtn = await screen.findByText("Finalizar");

    // Open the modal
    fireEvent.click(finalizarBtn);
    await screen.findByText("Finalizar Gerenciamento");

    // Confirm — fires updateGer.mutate, which receives a 401
    fireEvent.click(screen.getByText("Confirmar"));

    await waitFor(() =>
      expect(screen.getByText("Sessão expirada")).toBeInTheDocument()
    );
    expect(
      screen.getByText("Faça login novamente para continuar.")
    ).toBeInTheDocument();
  });

  it("shows 'Erro ao atualizar' toast when PATCH /api/gerenciamento/:id returns 500", async () => {
    setupApiFetch(500, 204);
    renderPage();

    const finalizarBtn = await screen.findByText("Finalizar");
    fireEvent.click(finalizarBtn);
    await screen.findByText("Finalizar Gerenciamento");
    fireEvent.click(screen.getByText("Confirmar"));

    await waitFor(() =>
      expect(screen.getByText("Erro ao atualizar")).toBeInTheDocument()
    );
    expect(
      screen.getByText("Não foi possível atualizar o gerenciamento. Tente novamente.")
    ).toBeInTheDocument();
  });
});

// ── deleteGer toast tests ─────────────────────────────────────────────────────

describe("GerenciamentoDetalhe – deleteGer onError toast", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/gerenciamento/1");
    // Remover button calls window.confirm() before mutating — return true automatically
    vi.stubGlobal("confirm", () => true);
  });

  afterEach(async () => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
    cleanup();
    await act(async () => { dispatch({ type: "REMOVE_TOAST" }); });
  });

  it("shows 'Sessão expirada' toast when DELETE /api/gerenciamento/:id returns 401", async () => {
    setupApiFetch(200, 401);
    renderPage();

    // Use role+name to be precise in case text appears in multiple elements
    const removerBtn = await screen.findByRole("button", { name: /Remover/i });
    fireEvent.click(removerBtn);

    await waitFor(() =>
      expect(screen.getByText("Sessão expirada")).toBeInTheDocument()
    );
    expect(
      screen.getByText("Faça login novamente para continuar.")
    ).toBeInTheDocument();
  });

  it("shows 'Erro ao excluir' toast when DELETE /api/gerenciamento/:id returns 500", async () => {
    setupApiFetch(200, 500);
    renderPage();

    const removerBtn = await screen.findByRole("button", { name: /Remover/i });
    fireEvent.click(removerBtn);

    await waitFor(() =>
      expect(screen.getByText("Erro ao excluir")).toBeInTheDocument()
    );
    expect(
      screen.getByText("Não foi possível excluir o gerenciamento. Tente novamente.")
    ).toBeInTheDocument();
  });
});
