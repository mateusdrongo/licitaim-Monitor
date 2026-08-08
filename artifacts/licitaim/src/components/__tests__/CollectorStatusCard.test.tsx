// @vitest-environment jsdom
/**
 * Smoke-tests for CollectorStatusCard:
 *  - Renders in all three health states (green / yellow / red) without runtime errors
 *  - "Executar agora" button is visible only for admin users
 *  - Per-portal breakdown renders when portals data is present
 */

import { vi } from "vitest";

// ─── Hoisted spy ─────────────────────────────────────────────────────────────
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
import React, { act } from "react";
import { render, screen, waitFor, cleanup, fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CollectorStatusCard } from "@/components/CollectorStatusCard";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function makeOk(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => body,
  } as unknown as Response;
}

function makeError(status = 500): Response {
  return {
    ok: false,
    status,
    json: async () => ({}),
  } as unknown as Response;
}

function renderCard(isAdmin: boolean) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <CollectorStatusCard isAdmin={isAdmin} />
    </QueryClientProvider>,
  );
}

// ─── Fixtures ────────────────────────────────────────────────────────────────

const BASE_STATUS = {
  last_run: new Date(Date.now() - 5 * 60 * 1000).toISOString(), // 5 min ago
  processed: 120,
  errors: 0,
  next_run_in: 1800,
  is_stale: false,
  is_running: false,
  portals: [],
  alert_state: null,
};

const STATUS_GREEN = { ...BASE_STATUS };

const STATUS_YELLOW = { ...BASE_STATUS, errors: 3 };

const STATUS_RED_STALE = { ...BASE_STATUS, is_stale: true };

const STATUS_RED_NEVER = {
  ...BASE_STATUS,
  last_run: null,
  is_stale: true,
  is_running: false,
};

const PORTALS = [
  { portal: "pncp", last_run: new Date().toISOString(), processed: 80, errors: 0, next_run_in: 900 },
  { portal: "comprasnet", last_run: new Date().toISOString(), processed: 40, errors: 2, next_run_in: null },
];

// ─── Tests ───────────────────────────────────────────────────────────────────

describe("CollectorStatusCard – health states", () => {
  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it("renders green / Operacional when collector is healthy", async () => {
    apiFetchMock.mockResolvedValue(makeOk(STATUS_GREEN));

    renderCard(false);

    await waitFor(() =>
      expect(screen.getByText("Operacional")).toBeInTheDocument(),
    );

    // Stats are rendered
    expect(screen.getByText("120")).toBeInTheDocument();
    // No error label
    expect(screen.queryByText("Inativo")).not.toBeInTheDocument();
    expect(screen.queryByText("Com erros")).not.toBeInTheDocument();
  });

  it("renders yellow / Com erros when collector reports errors", async () => {
    apiFetchMock.mockResolvedValue(makeOk(STATUS_YELLOW));

    renderCard(false);

    await waitFor(() =>
      expect(screen.getByText("Com erros")).toBeInTheDocument(),
    );

    // Error count is highlighted
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("renders red / Inativo when collector is stale", async () => {
    apiFetchMock.mockResolvedValue(makeOk(STATUS_RED_STALE));

    renderCard(false);

    await waitFor(() =>
      expect(screen.getByText("Inativo")).toBeInTheDocument(),
    );
  });

  it("renders red / Nunca executou when last_run is null", async () => {
    apiFetchMock.mockResolvedValue(makeOk(STATUS_RED_NEVER));

    renderCard(false);

    await waitFor(() =>
      expect(screen.getByText("Nunca executou")).toBeInTheDocument(),
    );
  });

  it("renders an error message when the API call fails", async () => {
    apiFetchMock.mockResolvedValue(makeError(500));

    renderCard(false);

    await waitFor(() =>
      expect(
        screen.getByText("Não foi possível obter o status do collector."),
      ).toBeInTheDocument(),
    );
  });
});

describe("CollectorStatusCard – admin button visibility", () => {
  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it("shows the Executar agora button for admin users", async () => {
    apiFetchMock.mockResolvedValue(makeOk(STATUS_GREEN));

    renderCard(true);

    await waitFor(() =>
      expect(screen.getByText("Executar agora")).toBeInTheDocument(),
    );
  });

  it("hides the Executar agora button for non-admin users", async () => {
    apiFetchMock.mockResolvedValue(makeOk(STATUS_GREEN));

    renderCard(false);

    await waitFor(() =>
      expect(screen.getByText("Operacional")).toBeInTheDocument(),
    );

    expect(screen.queryByText("Executar agora")).not.toBeInTheDocument();
    expect(screen.queryByText("Iniciando…")).not.toBeInTheDocument();
  });
});

describe("CollectorStatusCard – Executar agora button disabled state", () => {
  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it("shows 'Coletando…' and disables the button when is_running is true", async () => {
    apiFetchMock.mockResolvedValue(
      makeOk({ ...BASE_STATUS, is_running: true }),
    );

    renderCard(true); // admin to make button visible

    // Wait for the loading state to resolve
    await waitFor(() =>
      expect(screen.getByText("Coletando…")).toBeInTheDocument(),
    );

    const btn = screen.getByRole("button", { name: /Coletando…/ });
    expect(btn).toBeDisabled();
    expect(screen.queryByText("Executar agora")).not.toBeInTheDocument();
  });

  it("shows 'Executar agora' and enables the button when is_running is false", async () => {
    apiFetchMock.mockResolvedValue(
      makeOk({ ...BASE_STATUS, is_running: false }),
    );

    renderCard(true);

    await waitFor(() =>
      expect(screen.getByText("Executar agora")).toBeInTheDocument(),
    );

    const btn = screen.getByRole("button", { name: /Executar agora/ });
    expect(btn).not.toBeDisabled();
  });

  it("shows 'Iniciando…' and disables the button while POST /collector/run is in flight", async () => {
    // Deferred promise — controls when the POST resolves
    let resolvePost!: (value: Response) => void;
    const postPromise = new Promise<Response>((res) => {
      resolvePost = res;
    });

    // First call = GET /collector/status → green idle state
    // Second call = POST /collector/run → hangs until we resolve
    apiFetchMock
      .mockResolvedValueOnce(makeOk(STATUS_GREEN))
      .mockReturnValueOnce(postPromise);

    renderCard(true);

    // Wait for the component to finish loading and show the idle button
    const btn = await waitFor(() =>
      screen.getByRole("button", { name: /Executar agora/ }),
    );
    expect(btn).not.toBeDisabled();

    // Click — handleRunNow fires; setIsTriggering(true) runs before the await
    fireEvent.click(btn);

    // Component re-renders with isTriggering=true → "Iniciando…" + disabled
    await waitFor(() =>
      expect(screen.getByText("Iniciando…")).toBeInTheDocument(),
    );
    const initBtn = screen.getByRole("button", { name: /Iniciando…/ });
    expect(initBtn).toBeDisabled();
    expect(screen.queryByText("Executar agora")).not.toBeInTheDocument();

    // The RefreshCw SVG inside the run button must be spinning
    const spinner = initBtn.querySelector("svg");
    expect(spinner).not.toBeNull();
    expect(spinner).toHaveClass("animate-spin");

    // Resolve the POST → finally block sets isTriggering back to false
    await act(async () => {
      resolvePost(makeOk({ message: "started" }));
    });

    // Button returns to idle "Executar agora" and is re-enabled
    await waitFor(() =>
      expect(screen.getByText("Executar agora")).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /Executar agora/ })).not.toBeDisabled();
  });
});

describe("CollectorStatusCard – per-portal breakdown", () => {
  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it("renders the portal breakdown section when portals data is present", async () => {
    apiFetchMock.mockResolvedValue(
      makeOk({ ...STATUS_GREEN, portals: PORTALS }),
    );

    renderCard(false);

    await waitFor(() =>
      expect(screen.getByText("Por portal")).toBeInTheDocument(),
    );

    expect(screen.getByText("PNCP")).toBeInTheDocument();
    expect(screen.getByText("ComprasNet")).toBeInTheDocument();
  });

  it("does not render the portal section when portals array is empty", async () => {
    apiFetchMock.mockResolvedValue(makeOk(STATUS_GREEN));

    renderCard(false);

    await waitFor(() =>
      expect(screen.getByText("Operacional")).toBeInTheDocument(),
    );

    expect(screen.queryByText("Por portal")).not.toBeInTheDocument();
  });

  it("shows an error count badge for portals that have errors", async () => {
    apiFetchMock.mockResolvedValue(
      makeOk({ ...STATUS_GREEN, portals: PORTALS }),
    );

    renderCard(false);

    // ComprasNet has 2 errors — a "✕ 2" marker should appear
    await waitFor(() =>
      expect(screen.getByText(/✕ 2/)).toBeInTheDocument(),
    );
  });
});

// ─── Alert-state badge ────────────────────────────────────────────────────────

describe("CollectorStatusCard – alert-state badge", () => {
  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  const ALERTED_AT = "2026-08-08T10:30:00.000Z";

  it("shows the amber alert badge when is_stale_alerted is true and alerted_at is set", async () => {
    apiFetchMock.mockResolvedValue(
      makeOk({
        ...STATUS_GREEN,
        alert_state: {
          is_stale_alerted: true,
          alerted_at: ALERTED_AT,
          recovered_at: null,
        },
      }),
    );

    renderCard(false);

    await waitFor(() =>
      expect(screen.getByText(/Alerta enviado em/)).toBeInTheDocument(),
    );
  });

  it("hides the badge when is_stale_alerted is false (collector has recovered)", async () => {
    apiFetchMock.mockResolvedValue(
      makeOk({
        ...STATUS_GREEN,
        alert_state: {
          is_stale_alerted: false,
          alerted_at: ALERTED_AT,
          recovered_at: "2026-08-08T11:00:00.000Z",
        },
      }),
    );

    renderCard(false);

    // Wait for the card body to render (stats are visible)
    await waitFor(() =>
      expect(screen.getByText("Operacional")).toBeInTheDocument(),
    );

    expect(screen.queryByText(/Alerta enviado em/)).not.toBeInTheDocument();
  });

  it("hides the badge when alert_state is undefined (older API response)", async () => {
    const { alert_state: _omit, ...statusWithoutAlert } = BASE_STATUS as typeof BASE_STATUS & { alert_state?: unknown };
    apiFetchMock.mockResolvedValue(makeOk(statusWithoutAlert));

    renderCard(false);

    await waitFor(() =>
      expect(screen.getByText("Operacional")).toBeInTheDocument(),
    );

    expect(screen.queryByText(/Alerta enviado em/)).not.toBeInTheDocument();
  });

  it("hides the badge when is_stale_alerted is true but alerted_at is null", async () => {
    apiFetchMock.mockResolvedValue(
      makeOk({
        ...STATUS_GREEN,
        alert_state: {
          is_stale_alerted: true,
          alerted_at: null,
          recovered_at: null,
        },
      }),
    );

    renderCard(false);

    await waitFor(() =>
      expect(screen.getByText("Operacional")).toBeInTheDocument(),
    );

    expect(screen.queryByText(/Alerta enviado em/)).not.toBeInTheDocument();
  });
});
