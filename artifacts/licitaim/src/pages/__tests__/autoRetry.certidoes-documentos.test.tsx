// @vitest-environment jsdom
/**
 * Verifies that the retry-2 policy on Certidões and Documentos:
 *  - suppresses PageErrorState on a single transient failure (retry kicks in)
 *  - shows    PageErrorState after all retries are exhausted
 *
 * Both pages use:
 *   retry: 2,
 *   retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10_000)
 *     attempt 0 → 1 000 ms,  attempt 1 → 2 000 ms
 *
 * We avoid fake timers (they freeze RTL's waitFor polling) and let real
 * timeouts run, extending waitFor/test timeouts accordingly.
 */

import { vi } from "vitest";

// ─── Hoisted spy (must precede vi.mock calls) ─────────────────────────────────

const { apiFetchMock } = vi.hoisted(() => ({
  apiFetchMock: vi.fn(),
}));

vi.mock("@/lib/apiFetch", () => ({
  apiFetch: apiFetchMock,
  dispatchOfflineEvent: vi.fn(),
  onOfflineEvent: vi.fn(() => () => {}),
  isNetworkError: vi.fn(() => false),
}));

// ─── Imports ──────────────────────────────────────────────────────────────────

import React from "react";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import Certidoes from "@/pages/Certidoes";
import Documentos from "@/pages/Documentos";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function makeOk(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as unknown as Response;
}

/** Renders the given element inside a fresh QueryClient.
 *  QC defaults retry:false so only explicit query-level retry options drive
 *  retry behaviour. */
function renderInQC(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// ─── Certidões ────────────────────────────────────────────────────────────────
//
// useCertidoes() → GET /api/certidoes → returns Certidao[]
// Empty success → renders "Nenhuma certidão cadastrada"
//
// retryDelay(0) = 1 000 ms; retryDelay(1) = 2 000 ms → 3 000 ms total

describe("Certidões – retry suppresses PageErrorState on a transient failure", () => {
  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it(
    "does not show PageErrorState while a retry is in flight after a single failure",
    async () => {
      // Controlled Promise for the retry call so we can inspect the in-flight state.
      let resolveRetry!: (value: Response) => void;
      const retryPromise = new Promise<Response>((resolve) => {
        resolveRetry = resolve;
      });

      // First apiFetch call rejects; the retry call returns the pending promise.
      apiFetchMock
        .mockRejectedValueOnce(new Error("network error"))
        .mockReturnValue(retryPromise);

      renderInQC(<Certidoes />);

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

      // Resolve the retry — the page should now render its (empty) content.
      resolveRetry(makeOk([]));
      await waitFor(
        () =>
          expect(
            screen.getByText("Nenhuma certidão cadastrada"),
          ).toBeInTheDocument(),
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

      renderInQC(<Certidoes />);

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

// ─── Documentos ───────────────────────────────────────────────────────────────
//
// Documentos useQuery → GET /api/documentos?… → returns { data: Documento[], total: number }
// Empty success → renders "Nenhum documento encontrado"
//
// retryDelay(0) = 1 000 ms; retryDelay(1) = 2 000 ms → 3 000 ms total

describe("Documentos – retry suppresses PageErrorState on a transient failure", () => {
  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it(
    "does not show PageErrorState while a retry is in flight after a single failure",
    async () => {
      // Controlled Promise for the retry call so we can inspect the in-flight state.
      let resolveRetry!: (value: Response) => void;
      const retryPromise = new Promise<Response>((resolve) => {
        resolveRetry = resolve;
      });

      // First apiFetch call rejects; the retry call returns the pending promise.
      apiFetchMock
        .mockRejectedValueOnce(new Error("network error"))
        .mockReturnValue(retryPromise);

      renderInQC(<Documentos />);

      // Wait for the retry to be dispatched.
      // retryDelay(0) = 1 000 ms; allow up to 3 500 ms.
      await waitFor(
        () => expect(apiFetchMock).toHaveBeenCalledTimes(2),
        { timeout: 3_500 },
      );

      // ── IN-FLIGHT CHECK ────────────────────────────────────────────────────
      // The retry is in-flight; PageErrorState must not be visible.
      expect(
        screen.queryByText("Sem conexão com o servidor"),
      ).not.toBeInTheDocument();
      expect(screen.queryByText("Tentar novamente")).not.toBeInTheDocument();

      // Resolve the retry — the page should now render its (empty) content.
      resolveRetry(makeOk({ data: [], total: 0 }));
      await waitFor(
        () =>
          expect(
            screen.getByText("Nenhum documento encontrado"),
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
      // Every apiFetch call rejects – 1 initial + 2 retries = 3 total failures.
      apiFetchMock.mockRejectedValue(new Error("network error"));

      renderInQC(<Documentos />);

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
