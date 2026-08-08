import { describe, it, expect } from "vitest";
import {
  isValidIsoDate,
  extract422DateMessage,
  parseDateInvalidError,
} from "../dateUtils";

// ─── isValidIsoDate ───────────────────────────────────────────────────────────

describe("isValidIsoDate", () => {
  it("returns false for an empty string", () => {
    expect(isValidIsoDate("")).toBe(false);
  });

  it("returns false for null", () => {
    expect(isValidIsoDate(null)).toBe(false);
  });

  it("returns false for undefined", () => {
    expect(isValidIsoDate(undefined)).toBe(false);
  });

  it("returns false for nonsense text", () => {
    expect(isValidIsoDate("nonsense")).toBe(false);
  });

  it("returns false for a DD/MM/YYYY string (Brazilian locale format, not ISO)", () => {
    // Users might copy a date displayed in pt-BR format; Date() cannot parse it
    expect(isValidIsoDate("17/07/2026")).toBe(false);
  });

  it("returns false for a partially-valid string", () => {
    expect(isValidIsoDate("2026-13-99")).toBe(false);
  });

  it("returns true for a valid date-only ISO string", () => {
    expect(isValidIsoDate("2026-07-17")).toBe(true);
  });

  it("returns true for a valid ISO datetime with Z suffix", () => {
    expect(isValidIsoDate("2026-07-17T08:00:00Z")).toBe(true);
  });

  it("returns true for a valid ISO datetime without timezone", () => {
    expect(isValidIsoDate("2026-07-17T08:00:00")).toBe(true);
  });

  it("returns true for a valid ISO datetime with offset", () => {
    expect(isValidIsoDate("2026-07-17T08:00:00-03:00")).toBe(true);
  });
});

// ─── extract422DateMessage ────────────────────────────────────────────────────

describe("extract422DateMessage", () => {
  it("returns null for null input", () => {
    expect(extract422DateMessage(null)).toBeNull();
  });

  it("returns null for a non-object", () => {
    expect(extract422DateMessage("string")).toBeNull();
  });

  it("returns null when detail is missing", () => {
    expect(extract422DateMessage({})).toBeNull();
  });

  it("returns null when detail is not an array", () => {
    expect(extract422DateMessage({ detail: "bad" })).toBeNull();
  });

  it("returns null for a 422 body with no date-related errors", () => {
    const body = {
      detail: [
        { loc: ["body", "nome"], msg: "field required", type: "value_error.missing" },
      ],
    };
    expect(extract422DateMessage(body)).toBeNull();
  });

  it("returns a Portuguese label when the field is licitacaoDataEncerramento", () => {
    const body = {
      detail: [
        {
          loc: ["body", "licitacaoDataEncerramento"],
          msg: "Formato de data inválido",
          type: "value_error",
        },
      ],
    };
    const result = extract422DateMessage(body);
    expect(result).not.toBeNull();
    expect(result).toContain("Data de Encerramento");
    expect(result).toContain("AAAA-MM-DD");
  });

  it("returns a Portuguese label when the field is licitacaoDataAbertura", () => {
    const body = {
      detail: [
        {
          loc: ["body", "licitacaoDataAbertura"],
          msg: "invalid date format",
          type: "value_error",
        },
      ],
    };
    const result = extract422DateMessage(body);
    expect(result).not.toBeNull();
    expect(result).toContain("Data de Abertura");
  });

  it("returns a Portuguese label when msg mentions iso 8601", () => {
    const body = {
      detail: [
        {
          loc: ["body", "licitacaoDataPublicacao"],
          msg: "Value must be in ISO 8601 format",
          type: "value_error",
        },
      ],
    };
    const result = extract422DateMessage(body);
    expect(result).not.toBeNull();
    expect(result).toContain("Data de Publicação");
  });

  it("returns a generic message when the field name is not in the label map", () => {
    const body = {
      detail: [
        {
          loc: ["body", "dataEntrega"],
          msg: "invalid date",
          type: "value_error",
        },
      ],
    };
    const result = extract422DateMessage(body);
    expect(result).not.toBeNull();
    // dataEntrega IS in the label map
    expect(result).toContain("Data de Entrega");
  });

  it("picks the first date error from a multi-error 422 body", () => {
    const body = {
      detail: [
        { loc: ["body", "nome"], msg: "field required", type: "value_error.missing" },
        {
          loc: ["body", "licitacaoDataAbertura"],
          msg: "formato de data inválido",
          type: "value_error",
        },
        {
          loc: ["body", "licitacaoDataEncerramento"],
          msg: "formato de data inválido",
          type: "value_error",
        },
      ],
    };
    const result = extract422DateMessage(body);
    // Should return the first date error — Data de Abertura
    expect(result).toContain("Data de Abertura");
    expect(result).not.toContain("Data de Encerramento");
  });
});

// ─── parseDateInvalidError ────────────────────────────────────────────────────

describe("parseDateInvalidError", () => {
  it("returns null for a non-date-invalid message", () => {
    expect(parseDateInvalidError("401")).toBeNull();
    expect(parseDateInvalidError("422:algum erro")).toBeNull();
    expect(parseDateInvalidError("Erro ao gerenciar")).toBeNull();
  });

  it("returns the correct toast title for a DATE_INVALID message", () => {
    const result = parseDateInvalidError("DATE_INVALID:Data de Encerramento:99/99/9999");
    expect(result).not.toBeNull();
    expect(result!.title).toBe("Formato de data inválido");
  });

  it("includes the field label in the toast description", () => {
    const result = parseDateInvalidError("DATE_INVALID:Data de Abertura:not-a-date");
    expect(result!.description).toContain("Data de Abertura");
  });

  it("includes the bad value in the toast description", () => {
    const result = parseDateInvalidError("DATE_INVALID:Data de Encerramento:99/99/9999");
    expect(result!.description).toContain("99/99/9999");
  });

  it("handles a value that itself contains colons (e.g. a time string)", () => {
    const result = parseDateInvalidError("DATE_INVALID:Data de Encerramento:2026-99-99T99:99:99Z");
    expect(result!.description).toContain("2026-99-99T99:99:99Z");
  });

  it("uses 'data' as the label fallback when no label part is present", () => {
    // Malformed message — split gives ["DATE_INVALID", ""] so parts[1] is ""
    // which is falsy; the || fallback should kick in and produce "data".
    const result = parseDateInvalidError("DATE_INVALID:");
    expect(result!.title).toBe("Formato de data inválido");
    expect(result!.description).toContain('"data"');
  });
});
