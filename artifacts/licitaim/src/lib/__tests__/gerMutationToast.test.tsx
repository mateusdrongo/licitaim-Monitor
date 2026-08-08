// @vitest-environment jsdom
/**
 * Integration test: verify that the gerMutation onError code path — which calls
 * parseDateInvalidError() + toast() — produces a visible destructive toast in
 * the DOM when a tender carries an invalid date string.
 *
 * The test renders <Toaster /> (the same component used in the real app) and
 * triggers the exact handler logic, then asserts that the rendered Portuguese
 * title and description appear in the document.
 */
import React, { act } from "react";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import { toast, dispatch } from "@/hooks/use-toast";
import { isValidIsoDate, parseDateInvalidError } from "@/lib/dateUtils";

// ── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Mirrors the relevant part of gerMutation.onError in Licitacoes.tsx.
 * Returns true when a date-invalid toast was dispatched.
 */
function simulateGerOnError(errorMsg: string): boolean {
  const dateToast = parseDateInvalidError(errorMsg);
  if (dateToast) {
    toast({ variant: "destructive", ...dateToast });
    return true;
  }
  return false;
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("gerMutation onError – DATE_INVALID toast (integration)", () => {
  let cleanup: (() => void) | null = null;

  beforeEach(() => {
    // Render the Toaster once per test inside beforeEach so we always start
    // with a fresh DOM tree and a fresh subscription to the global toast state.
    const { unmount } = render(<Toaster />);
    cleanup = unmount;
  });

  afterEach(() => {
    // Reset global toast state so tests don't bleed into each other.
    act(() => dispatch({ type: "REMOVE_TOAST" }));
    cleanup?.();
    cleanup = null;
  });

  it("renders a destructive toast with the correct title when dataEncerramento is a bad date", async () => {
    // Arrange: construct the error message exactly as gerMutation throws it
    const badDate = "99/99/9999";
    const label = "Data de Encerramento";
    const errMsg = `DATE_INVALID:${label}:${badDate}`;

    // Pre-condition: isValidIsoDate must reject this value so the real code
    // would actually throw this error in the first place.
    expect(isValidIsoDate(badDate)).toBe(false);

    // Act: run the handler inside act() so React flushes state updates
    await act(async () => {
      simulateGerOnError(errMsg);
    });

    // Assert: the toast title and description should be in the document
    expect(screen.getByText("Formato de data inválido")).toBeInTheDocument();
    expect(screen.getByText(/99\/99\/9999/)).toBeInTheDocument();
    expect(screen.getByText(/Data de Encerramento/)).toBeInTheDocument();
  });

  it("renders a destructive toast with the correct title when dataAbertura is a bad date", async () => {
    const badDate = "17-07-2026"; // DD-MM-YYYY — invalid for Date()
    const label = "Data de Abertura";
    const errMsg = `DATE_INVALID:${label}:${badDate}`;

    expect(isValidIsoDate(badDate)).toBe(false);

    await act(async () => {
      simulateGerOnError(errMsg);
    });

    expect(screen.getByText("Formato de data inválido")).toBeInTheDocument();
    expect(screen.getByText(/17-07-2026/)).toBeInTheDocument();
    expect(screen.getByText(/Data de Abertura/)).toBeInTheDocument();
  });

  it("does NOT dispatch a date toast for a non-date error message", async () => {
    const dispatched = simulateGerOnError("401");
    expect(dispatched).toBe(false);
    // No toast title should appear in the document
    expect(screen.queryByText("Formato de data inválido")).not.toBeInTheDocument();
  });
});
