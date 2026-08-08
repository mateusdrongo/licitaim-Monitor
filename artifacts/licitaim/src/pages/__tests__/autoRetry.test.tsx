// @vitest-environment jsdom
/**
 * Verifies that the retry-2 policy on Dashboard and Agenda:
 *  - suppresses PageErrorState on a single transient failure (retry kicks in)
 *  - shows    PageErrorState after all retries are exhausted
 *
 * Dashboard  – retry config lives inside the useGetDashboard call; the mock
 *              wires it through to a real useQuery with retryDelay:0 so the
 *              tests run without needing fake timers.
 *
 * Agenda     – retry config lives inside the useAgenda hook (retryDelay uses
 *              real setTimeout). Tests wait for retryDelay(0)=1 000 ms with
 *              extended waitFor timeouts.
 *
 * Both success cases use a controlled Promise for the retry call so the
 * in-flight retry state can be inspected before the promise resolves.
 */

import { vi } from "vitest";

// ─── Hoisted spies (must precede vi.mock calls) ───────────────────────────────

const { dashboardQueryFn, apiFetchMock } = vi.hoisted(() => ({
  dashboardQueryFn: vi.fn(),
  apiFetchMock: vi.fn(),
}));

// Mock useGetDashboard: wire retry/queryKey through from the component's own
// hook options (so removing retry:2 from Dashboard would break the test), but
// force retryDelay:0 so retries are instant. When retry is absent the QC
// default (retry:false) applies — no ?? fallback.
vi.mock("@workspace/api-client-react", async () => {
  const { useQuery } = await import("@tanstack/react-query");
  return {
    useGetDashboard: ({ query }: { query?: Record<string, unknown> } = {}) =>
      useQuery({
        queryKey:
          (query?.queryKey as readonly unknown[]) ?? (["dashboard"] as const),
        queryFn: dashboardQueryFn,
        retry: query?.retry as number | boolean | undefined,
        retryDelay: 0, // instant retries – no timer advancement needed
      }),
  };
});

vi.mock("@/lib/apiFetch", () => ({
  apiFetch: apiFetchMock,
  dispatchOfflineEvent: vi.fn(),
  onOfflineEvent: vi.fn(() => () => {}),
  isNetworkError: vi.fn(() => false),
}));

// Recharts uses browser APIs absent in jsdom – replace with a thin stub.
vi.mock("recharts", () => ({
  PieChart: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="piechart">{children}</div>
  ),
  Pie: () => null,
  Cell: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

vi.mock("wouter", () => ({
  Link: ({
    children,
    href,
  }: {
    children?: React.ReactNode;
    href?: string;
  }) => <a href={href}>{children}</a>,
  useLocation: () => ["/", () => {}],
}));

vi.mock("@/components/CollectorStatusCard", () => ({
  CollectorStatusCard: () => null,
}));

// ─── Imports ──────────────────────────────────────────────────────────────────

import React from "react";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import Dashboard from "@/pages/Dashboard";
import Agenda from "@/pages/Agenda";

// ─── Fixtures ────────────────────────────────────────────────────────────────

const MOCK_DASHBOARD = {
  valorTotalPipeline: 0,
  totalOportunidades: 0,
  totalAlertasNaoLidos: 0,
  totalMonitoramentos: 0,
  totalFavoritos: 0,
  licitacoesRecentes: [],
  alertas: [],
  licitacoesPorUf: [],
  novasOportunidadesHoje: 0,
  oportunidadesVigentes: 0,
  iminenciaEncerramento: 0,
  novosAndamentos: 0,
  certidoesVencendo: 0,
  documentosPendentes: 0,
};

const MOCK_AGENDA = {
  eventos: [],
  resumo: { total: 0, criticos: 0, atencao: 0, proximos7dias: 0 },
};

function makeOk(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as unknown as Response;
}

/** Renders the given element inside a fresh QueryClient. QC defaults retry:false
 *  so only explicit query-level retry options drive retry behaviour. */
function renderInQC(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

describe("Dashboard – retry suppresses PageErrorState on a transient failure", () => {
  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it("does not show PageErrorState while a retry is in flight after a single failure", async () => {
    // Use a controlled Promise for the retry call so we can inspect the
    // in-flight state before it resolves.
    let resolveRetry!: (value: typeof MOCK_DASHBOARD) => void;
    const retryPromise = new Promise<typeof MOCK_DASHBOARD>((resolve) => {
      resolveRetry = resolve;
    });

    // First call rejects; second call (the retry) returns the pending promise.
    dashboardQueryFn
      .mockRejectedValueOnce(new Error("network error"))
      .mockReturnValue(retryPromise);

    // Secondary queries (admin-stats, agenda) resolve immediately.
    apiFetchMock.mockResolvedValue(makeOk({ is_admin: false }));

    renderInQC(<Dashboard />);

    // Wait for the retry to have been dispatched.
    // retryDelay:0 means it fires immediately after the first rejection.
    await waitFor(() => expect(dashboardQueryFn).toHaveBeenCalledTimes(2));

    // ── IN-FLIGHT CHECK ──────────────────────────────────────────────────────
    // The retry is now pending (retryPromise unresolved). PageErrorState must
    // NOT be shown while the retry is still in progress.
    expect(
      screen.queryByText("Sem conexão com o servidor"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Tentar novamente")).not.toBeInTheDocument();

    // Resolve the retry — the dashboard should now render its data.
    resolveRetry(MOCK_DASHBOARD);
    await waitFor(() =>
      expect(screen.getByText("Visão Geral")).toBeInTheDocument(),
    );

    // Confirm error state is still absent after successful completion.
    expect(
      screen.queryByText("Sem conexão com o servidor"),
    ).not.toBeInTheDocument();
  });

  it("shows PageErrorState once all retries (retry:2) are exhausted", async () => {
    // Every call fails – 1 initial + 2 retries all reject.
    // With retryDelay:0, all three happen near-instantly.
    dashboardQueryFn.mockRejectedValue(new Error("network error"));
    apiFetchMock.mockResolvedValue(makeOk({ is_admin: false }));

    renderInQC(<Dashboard />);

    // All 3 attempts fail → isError becomes true → PageErrorState is shown.
    await waitFor(() =>
      expect(
        screen.getByText("Sem conexão com o servidor"),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText("Tentar novamente")).toBeInTheDocument();
    // 1 initial + 2 retries = 3 total queryFn invocations.
    expect(dashboardQueryFn).toHaveBeenCalledTimes(3);
  });
});

// ─── Agenda ───────────────────────────────────────────────────────────────────
//
// Agenda's useAgenda hook sets retryDelay: (attempt) => min(1000*2^attempt, 10000)
//   attempt 0 → 1 000 ms,  attempt 1 → 2 000 ms
//
// We avoid fake timers (they freeze RTL's waitFor polling) and let real
// timeouts run, extending waitFor/test timeouts accordingly.

describe("Agenda – retry suppresses PageErrorState on a transient failure", () => {
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

      renderInQC(<Agenda />);

      // Wait for the retry to be dispatched.
      // retryDelay(0) = 1 000 ms; allow up to 3 500 ms.
      await waitFor(
        () => expect(apiFetchMock).toHaveBeenCalledTimes(2),
        { timeout: 3_500 },
      );

      // ── IN-FLIGHT CHECK ────────────────────────────────────────────────────
      // The retry is now in-flight (retryPromise unresolved). During this window
      // react-query keeps isError:false, so PageErrorState must not be visible.
      expect(
        screen.queryByText("Sem conexão com o servidor"),
      ).not.toBeInTheDocument();
      expect(screen.queryByText("Tentar novamente")).not.toBeInTheDocument();

      // Resolve the retry — the agenda should now render its (empty) state.
      resolveRetry(makeOk(MOCK_AGENDA));
      await waitFor(
        () => expect(screen.getByText("Agenda limpa")).toBeInTheDocument(),
        { timeout: 3_500 },
      );

      // Error state still absent after successful completion.
      expect(
        screen.queryByText("Sem conexão com o servidor"),
      ).not.toBeInTheDocument();
    },
    12_000, // test-level timeout: 1 000 ms retryDelay + margin
  );

  it(
    "shows PageErrorState once all retries (retry:2) are exhausted",
    async () => {
      // Every apiFetch call rejects – 1 initial + 2 retries = 3 total failures.
      // Total retryDelay: 1 000 ms (attempt 0) + 2 000 ms (attempt 1) = 3 000 ms.
      apiFetchMock.mockRejectedValue(new Error("network error"));

      renderInQC(<Agenda />);

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
    15_000, // test-level timeout
  );
});
