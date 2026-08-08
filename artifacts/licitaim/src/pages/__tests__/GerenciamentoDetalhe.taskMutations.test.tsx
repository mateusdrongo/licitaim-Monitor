// @vitest-environment jsdom
/**
 * Integration tests: render GerenciamentoDetalhe with mocked apiFetch,
 * trigger toggleTarefa (checkbox click) and deleteTarefa (trash click),
 * and assert that the correct destructive toast fires on 401 vs non-401 errors.
 *
 * Pattern mirrors GerenciamentoDetalhe.updateDelete.test.tsx.
 */

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

const MOCK_GER = {
  id: 1,
  licitacaoId: "licit-1",
  licitacaoObjeto: "Objeto de teste",
  status: "em_andamento",
  totalTarefas: 1,
  tarefasConcluidas: 0,
  totalAnotacoes: 0,
  criadoEm: "2026-01-01T00:00:00Z",
  atualizadoEm: "2026-01-01T00:00:00Z",
};

const MOCK_TAREFA = {
  id: 1,
  gerenciamentoId: 1,
  titulo: "Tarefa de teste",
  concluida: false,
  prioridade: "normal",
  categoria: "geral",
  criadoEm: "2026-01-01T00:00:00Z",
};

/**
 * Sets up apiFetch so:
 *  - All GETs return valid fixtures (one tarefa in the list).
 *  - PATCH  .../tarefas/:id  → toggleStatus
 *  - DELETE .../tarefas/:id  → deleteStatus
 */
function setupApiFetch(toggleStatus: number, deleteStatus: number) {
  vi.mocked(apiFetch).mockImplementation(async (input, init?) => {
    const url = input.toString();
    const method = (init?.method ?? "GET").toUpperCase();

    // Tarefa mutations (more specific path checked first)
    if (method === "PATCH" && /\/api\/gerenciamento\/\d+\/tarefas\/\d+/.test(url)) {
      return makeResponse(toggleStatus);
    }
    if (method === "DELETE" && /\/api\/gerenciamento\/\d+\/tarefas\/\d+/.test(url)) {
      return makeResponse(deleteStatus);
    }

    // Sub-resource GETs
    if (/\/api\/gerenciamento\/\d+\/tarefas/.test(url))
      return makeResponse(200, { data: [MOCK_TAREFA] });
    if (/\/api\/gerenciamento\/\d+\/anotacoes/.test(url))
      return makeResponse(200, { data: [] });
    if (/\/api\/gerenciamento\/\d+\/habilitacao/.test(url))
      return makeResponse(200, { data: [] });
    if (/\/api\/alertas/.test(url)) return makeResponse(200, { data: [] });

    // Main gerenciamento GET
    if (/\/api\/gerenciamento\/\d+$/.test(url)) return makeResponse(200, MOCK_GER);

    return makeResponse(404);
  });
}

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
    </QueryClientProvider>,
  );
}

// ── toggleTarefa toast tests ──────────────────────────────────────────────────

describe("GerenciamentoDetalhe – toggleTarefa onError toast", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/gerenciamento/1");
  });

  afterEach(async () => {
    vi.clearAllMocks();
    cleanup();
    await act(async () => { dispatch({ type: "REMOVE_TOAST" }); });
  });

  it("shows 'Sessão expirada' toast when PATCH tarefas/:id returns 401", async () => {
    setupApiFetch(401, 204);
    renderPage();

    // Wait for the tarefa to appear in the list
    await screen.findByText("Tarefa de teste");

    // Click the toggle (checkbox) button for the tarefa
    fireEvent.click(
      screen.getByRole("button", { name: "Marcar tarefa como concluída" }),
    );

    await waitFor(() =>
      expect(screen.getByText("Sessão expirada")).toBeInTheDocument(),
    );
    expect(
      screen.getByText("Faça login novamente para continuar."),
    ).toBeInTheDocument();
  });

  it("shows 'Erro ao atualizar tarefa' toast when PATCH tarefas/:id returns 500", async () => {
    setupApiFetch(500, 204);
    renderPage();

    await screen.findByText("Tarefa de teste");

    fireEvent.click(
      screen.getByRole("button", { name: "Marcar tarefa como concluída" }),
    );

    await waitFor(() =>
      expect(screen.getByText("Erro ao atualizar tarefa")).toBeInTheDocument(),
    );
    expect(
      screen.getByText("Não foi possível marcar a tarefa. Tente novamente."),
    ).toBeInTheDocument();
  });
});

// ── deleteTarefa toast tests ──────────────────────────────────────────────────

describe("GerenciamentoDetalhe – deleteTarefa onError toast", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/gerenciamento/1");
  });

  afterEach(async () => {
    vi.clearAllMocks();
    cleanup();
    await act(async () => { dispatch({ type: "REMOVE_TOAST" }); });
  });

  it("shows 'Sessão expirada' toast when DELETE tarefas/:id returns 401", async () => {
    setupApiFetch(200, 401);
    renderPage();

    await screen.findByText("Tarefa de teste");

    fireEvent.click(screen.getByRole("button", { name: "Excluir tarefa" }));

    await waitFor(() =>
      expect(screen.getByText("Sessão expirada")).toBeInTheDocument(),
    );
    expect(
      screen.getByText("Faça login novamente para continuar."),
    ).toBeInTheDocument();
  });

  it("shows 'Erro ao excluir tarefa' toast when DELETE tarefas/:id returns 500", async () => {
    setupApiFetch(200, 500);
    renderPage();

    await screen.findByText("Tarefa de teste");

    fireEvent.click(screen.getByRole("button", { name: "Excluir tarefa" }));

    await waitFor(() =>
      expect(screen.getByText("Erro ao excluir tarefa")).toBeInTheDocument(),
    );
    expect(
      screen.getByText("Não foi possível excluir a tarefa. Tente novamente."),
    ).toBeInTheDocument();
  });
});
