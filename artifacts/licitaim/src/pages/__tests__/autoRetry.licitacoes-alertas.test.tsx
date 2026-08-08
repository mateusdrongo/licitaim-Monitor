// @vitest-environment jsdom
/**
 * Verifies that the retry-2 policy on Licitacoes and Alertas:
 *  - suppresses PageErrorState on a single transient failure (retry kicks in)
 *  - shows    PageErrorState after all retries are exhausted
 *
 * Both pages use:
 *   retry: 2,
 *   retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10_000)
 *     attempt 0 → 1 000 ms,  attempt 1 → 2 000 ms
 *
 * Real timeouts are used (same pattern as Agenda in autoRetry.test.tsx).
 * waitFor/test timeouts are extended accordingly.
 */

import { vi } from "vitest";

// ─── Hoisted spies ────────────────────────────────────────────────────────────
// licitacoesFn is a dedicated spy for the main /api/licitacoes?... call so we
// can count retries without counting the secondary background queries.

const { apiFetchMock, licitacoesFn } = vi.hoisted(() => ({
  apiFetchMock: vi.fn(),
  licitacoesFn: vi.fn(),
}));

// ─── Module mocks ─────────────────────────────────────────────────────────────

vi.mock("@/lib/apiFetch", () => ({
  apiFetch: apiFetchMock,
  dispatchOfflineEvent: vi.fn(),
  onOfflineEvent: vi.fn(() => () => {}),
  isNetworkError: vi.fn(() => false),
}));

// Wire useListAlertas through to a real useQuery, forwarding the component's
// own retry/retryDelay options so removing them from Alertas.tsx would break
// this test. queryFn delegates to apiFetchMock so the same spy controls failures.
vi.mock("@workspace/api-client-react", async () => {
  const { useQuery } = await import("@tanstack/react-query");
  return {
    useListAlertas: (
      _params: unknown,
      opts: { query?: Record<string, unknown> } = {},
    ) => {
      const q = (opts?.query ?? {}) as Record<string, unknown>;
      return useQuery({
        queryKey: (q.queryKey as readonly unknown[]) ?? ["alertas"],
        queryFn: async () => {
          const res = await apiFetchMock("/api/alertas");
          return (res as Response).json();
        },
        retry: q.retry as number | boolean | undefined,
        retryDelay: q.retryDelay as ((attempt: number) => number) | undefined,
      });
    },
    useMarcarAlertaLido: () => ({ mutate: vi.fn(), isPending: false }),
    useMarcarTodosAlertasLidos: () => ({
      mutate: vi.fn(),
      isPending: false,
      data: undefined,
    }),
    getListAlertasQueryKey: (_p?: unknown) => ["alertas"],
    getGetDashboardQueryKey: () => ["dashboard"],
  };
});

// Licitacoes uses useSearch + useLocation + Link from wouter.
// useSearch returns "s=1" so url.submitted=true and the main query is enabled.
vi.mock("wouter", () => ({
  Link: ({
    children,
    href,
  }: {
    children?: React.ReactNode;
    href?: string;
  }) => <a href={href}>{children}</a>,
  useLocation: () => ["/licitacoes", () => {}],
  useSearch: () => "s=1",
}));

// ─── Imports ──────────────────────────────────────────────────────────────────

import React from "react";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import Licitacoes from "@/pages/Licitacoes";
import Alertas from "@/pages/Alertas";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function makeOk(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as unknown as Response;
}

function renderInQC(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// ─── Licitacoes setup ─────────────────────────────────────────────────────────
//
// apiFetch is called by several background queries (favoritos, gerenciamento,
// stats — all retry:false) in addition to the main licitacoes query.
// We route the main licitacoes endpoint through `licitacoesFn` so we can count
// retries precisely without counting the secondary calls.

function setupLicitacoesApiFetch() {
  apiFetchMock.mockImplementation(async (input: RequestInfo | URL) => {
    const url = input.toString();

    // Main licitacoes query — has query-string params immediately after the path
    if (/\/api\/licitacoes\?/.test(url)) {
      return licitacoesFn(url);
    }

    // Admin stats (retry:false — returns non-admin so collector query stays disabled)
    if (/\/api\/licitacoes\/admin\/stats/.test(url)) {
      return makeOk({
        total: 0,
        last_sync: null,
        fonte_predominante: null,
        is_admin: false,
      });
    }

    // All other background queries (favoritos, gerenciamento, collector, …)
    return makeOk({ data: [] });
  });
}

// ─── Licitacoes ──────────────────────────────────────────────────────────────
//
// useLicitacoes retryDelay(0) = 1 000 ms; retryDelay(1) = 2 000 ms

describe("Licitacoes – retry suppresses PageErrorState on a transient failure", () => {
  beforeEach(() => {
    setupLicitacoesApiFetch();
  });

  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it(
    "does not show PageErrorState while a retry is in flight after a single failure",
    async () => {
      // Controlled Promise for the retry call so we can inspect in-flight state.
      let resolveRetry!: (value: Response) => void;
      const retryPromise = new Promise<Response>((resolve) => {
        resolveRetry = resolve;
      });

      // First licitacoes call rejects; the retry returns the pending promise.
      licitacoesFn
        .mockRejectedValueOnce(new Error("network error"))
        .mockReturnValue(retryPromise);

      renderInQC(<Licitacoes />);

      // Wait for the retry to be dispatched.
      // retryDelay(0) = 1 000 ms; allow up to 3 500 ms.
      await waitFor(
        () => expect(licitacoesFn).toHaveBeenCalledTimes(2),
        { timeout: 3_500 },
      );

      // ── IN-FLIGHT CHECK ────────────────────────────────────────────────────
      // During the retry react-query keeps isError:false → PageErrorState hidden.
      expect(
        screen.queryByText("Sem conexão com o servidor"),
      ).not.toBeInTheDocument();
      expect(screen.queryByText("Tentar novamente")).not.toBeInTheDocument();

      // Resolve the retry — page should render the empty-result state.
      resolveRetry(
        makeOk({ data: [], total: 0, page: 1, total_pages: 1, source: "banco" }),
      );
      await waitFor(
        () =>
          expect(
            screen.getByText("Nenhuma licitação encontrada"),
          ).toBeInTheDocument(),
        { timeout: 3_500 },
      );

      // Error state still absent after successful completion.
      expect(
        screen.queryByText("Sem conexão com o servidor"),
      ).not.toBeInTheDocument();
    },
    12_000,
  );

  it(
    "shows PageErrorState once all retries (retry:2) are exhausted",
    async () => {
      // Every licitacoes call rejects — 1 initial + 2 retries = 3 total.
      // Total retryDelay: 1 000 ms + 2 000 ms = 3 000 ms.
      licitacoesFn.mockRejectedValue(new Error("network error"));

      renderInQC(<Licitacoes />);

      // Allow 8 s for all retries to exhaust.
      await waitFor(
        () =>
          expect(
            screen.getByText("Sem conexão com o servidor"),
          ).toBeInTheDocument(),
        { timeout: 8_000 },
      );
      expect(screen.getByText("Tentar novamente")).toBeInTheDocument();
      // 1 initial + 2 retries = 3 total licitacoes queryFn invocations.
      expect(licitacoesFn).toHaveBeenCalledTimes(3);
    },
    15_000,
  );
});

// ─── Alertas ─────────────────────────────────────────────────────────────────
//
// useListAlertas retryDelay(0) = 1 000 ms; retryDelay(1) = 2 000 ms.
// apiFetchMock is called directly from the mocked useListAlertas queryFn.

describe("Alertas – retry suppresses PageErrorState on a transient failure", () => {
  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it(
    "does not show PageErrorState while a retry is in flight after a single failure",
    async () => {
      // Controlled Promise for the retry call so we can inspect in-flight state.
      let resolveRetry!: (value: Response) => void;
      const retryPromise = new Promise<Response>((resolve) => {
        resolveRetry = resolve;
      });

      // First apiFetch call rejects; the retry call returns the pending promise.
      apiFetchMock
        .mockRejectedValueOnce(new Error("network error"))
        .mockReturnValue(retryPromise);

      renderInQC(<Alertas />);

      // Wait for the retry to be dispatched.
      // retryDelay(0) = 1 000 ms; allow up to 3 500 ms.
      await waitFor(
        () => expect(apiFetchMock).toHaveBeenCalledTimes(2),
        { timeout: 3_500 },
      );

      // ── IN-FLIGHT CHECK ────────────────────────────────────────────────────
      // During the retry react-query keeps isError:false → PageErrorState hidden.
      expect(
        screen.queryByText("Sem conexão com o servidor"),
      ).not.toBeInTheDocument();
      expect(screen.queryByText("Tentar novamente")).not.toBeInTheDocument();

      // Resolve the retry — page should render the empty-inbox state.
      resolveRetry(makeOk({ data: [], totalNaoLidos: 0 }));
      await waitFor(
        () =>
          expect(
            screen.getByText("Caixa de entrada limpa"),
          ).toBeInTheDocument(),
        { timeout: 3_500 },
      );

      // Error state still absent after successful completion.
      expect(
        screen.queryByText("Sem conexão com o servidor"),
      ).not.toBeInTheDocument();
    },
    12_000,
  );

  it(
    "shows PageErrorState once all retries (retry:2) are exhausted",
    async () => {
      // Every apiFetch call rejects — 1 initial + 2 retries = 3 total failures.
      // Total retryDelay: 1 000 ms + 2 000 ms = 3 000 ms.
      apiFetchMock.mockRejectedValue(new Error("network error"));

      renderInQC(<Alertas />);

      // Allow 8 s for all retries to exhaust.
      await waitFor(
        () =>
          expect(
            screen.getByText("Sem conexão com o servidor"),
          ).toBeInTheDocument(),
        { timeout: 8_000 },
      );
      expect(screen.getByText("Tentar novamente")).toBeInTheDocument();
      // 1 initial + 2 retries = 3 total apiFetch invocations.
      expect(apiFetchMock).toHaveBeenCalledTimes(3);
    },
    15_000,
  );
});
