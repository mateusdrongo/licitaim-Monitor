// @vitest-environment jsdom
/**
 * Confirms the session spinner on /entrar and /cadastro:
 *  - is visible while useGetMe is loading
 *  - disappears and shows the form when useGetMe errors (network failure,
 *    server 500, or any rejection) so users are never stuck on the spinner
 *
 * useGetMe is fully mocked; this isolates Login/Cadastro rendering logic
 * from the real HTTP layer and React Query internals.
 */

import { vi } from "vitest";

// ─── Hoisted spies (must precede vi.mock calls) ────────────────────────────

const { useGetMeMock, apiFetchMock } = vi.hoisted(() => ({
  useGetMeMock: vi.fn(),
  apiFetchMock: vi.fn(),
}));

vi.mock("@workspace/api-client-react", () => ({
  useGetMe: useGetMeMock,
}));

vi.mock("@/lib/apiFetch", () => ({
  apiFetch: apiFetchMock,
  dispatchOfflineEvent: vi.fn(),
  onOfflineEvent: vi.fn(() => () => {}),
  isNetworkError: vi.fn(() => false),
}));

// wouter hooks – provide stable stubs so components don't throw
vi.mock("wouter", () => ({
  useLocation: () => ["/entrar", vi.fn()],
  useSearch: () => "",
}));

import React from "react";
import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import Login from "@/pages/Login";
import Cadastro from "@/pages/Cadastro";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ─── Helpers ───────────────────────────────────────────────────────────────

/** Simulate useGetMe still in flight (initial load) */
function mockLoading() {
  useGetMeMock.mockReturnValue({ data: undefined, isLoading: true, refetch: vi.fn() });
}

/** Simulate useGetMe settled with a network error (no user, isLoading:false) */
function mockNetworkError() {
  useGetMeMock.mockReturnValue({
    data: undefined,
    isLoading: false,
    error: new Error("Network error"),
    refetch: vi.fn(),
  });
}

/** Simulate useGetMe settled with a server 500 (treated same as error) */
function mockServerError() {
  useGetMeMock.mockReturnValue({
    data: undefined,
    isLoading: false,
    error: new Error("Internal Server Error"),
    refetch: vi.fn(),
  });
}

/** Visible text the spinner shows */
const SPINNER_TEXT = "Verificando sessão…";

// ───────────────────────────────────────────────────────────────────────────
// Login page
// ───────────────────────────────────────────────────────────────────────────

describe("Login – session spinner behaviour", () => {
  describe("while useGetMe is loading", () => {
    beforeEach(() => mockLoading());

    it("shows the 'Verificando sessão…' spinner", () => {
      render(<Login />);
      expect(screen.getByText(SPINNER_TEXT)).toBeInTheDocument();
    });

    it("hides the login form while loading", () => {
      render(<Login />);
      expect(screen.queryByRole("button", { name: /Acessar Plataforma/i })).not.toBeInTheDocument();
    });
  });

  describe("when useGetMe errors with a network failure", () => {
    beforeEach(() => mockNetworkError());

    it("removes the spinner", () => {
      render(<Login />);
      expect(screen.queryByText(SPINNER_TEXT)).not.toBeInTheDocument();
    });

    it("shows the login form so the user is not stuck", () => {
      render(<Login />);
      expect(screen.getByRole("button", { name: /Acessar Plataforma/i })).toBeInTheDocument();
    });

    it("shows the email and password inputs", () => {
      render(<Login />);
      expect(screen.getByLabelText(/E-mail corporativo/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Senha/i)).toBeInTheDocument();
    });
  });

  describe("when useGetMe errors with a server error (500)", () => {
    beforeEach(() => mockServerError());

    it("removes the spinner", () => {
      render(<Login />);
      expect(screen.queryByText(SPINNER_TEXT)).not.toBeInTheDocument();
    });

    it("shows the login form", () => {
      render(<Login />);
      expect(screen.getByRole("button", { name: /Acessar Plataforma/i })).toBeInTheDocument();
    });
  });
});

// ───────────────────────────────────────────────────────────────────────────
// Cadastro page
// ───────────────────────────────────────────────────────────────────────────

describe("Cadastro – session spinner behaviour", () => {
  describe("while useGetMe is loading", () => {
    beforeEach(() => mockLoading());

    it("shows the 'Verificando sessão…' spinner", () => {
      render(<Cadastro />);
      expect(screen.getByText(SPINNER_TEXT)).toBeInTheDocument();
    });

    it("hides the register form while loading", () => {
      render(<Cadastro />);
      expect(screen.queryByRole("button", { name: /Criar conta grátis/i })).not.toBeInTheDocument();
    });
  });

  describe("when useGetMe errors with a network failure", () => {
    beforeEach(() => mockNetworkError());

    it("removes the spinner", () => {
      render(<Cadastro />);
      expect(screen.queryByText(SPINNER_TEXT)).not.toBeInTheDocument();
    });

    it("shows the register form so the user is not stuck", () => {
      render(<Cadastro />);
      expect(screen.getByRole("button", { name: /Criar conta grátis/i })).toBeInTheDocument();
    });

    it("shows the name, email and password inputs", () => {
      render(<Cadastro />);
      expect(screen.getByLabelText(/Nome completo/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/E-mail corporativo/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Senha/i)).toBeInTheDocument();
    });
  });

  describe("when useGetMe errors with a server error (500)", () => {
    beforeEach(() => mockServerError());

    it("removes the spinner", () => {
      render(<Cadastro />);
      expect(screen.queryByText(SPINNER_TEXT)).not.toBeInTheDocument();
    });

    it("shows the register form", () => {
      render(<Cadastro />);
      expect(screen.getByRole("button", { name: /Criar conta grátis/i })).toBeInTheDocument();
    });
  });
});
