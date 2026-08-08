/**
 * Utilitários de formatação de data/hora para o fuso America/Fortaleza (BRT, UTC-3).
 *
 * Regra: use estas funções sempre que o valor vier do backend como ISO 8601 com
 * componente de hora (ex.: "2026-08-06T22:15:00Z" ou "2026-08-06T22:15:00").
 * Para strings de data pura (YYYY-MM-DD) sem hora, use new Date(s + "T12:00:00")
 * com toLocaleDateString("pt-BR") normalmente — não é necessário fuso nesses casos.
 */

const TZ = "America/Fortaleza"; // UTC-3 (sem horário de verão)

const OPT_DATE: Intl.DateTimeFormatOptions = {
  timeZone: TZ,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
};

const OPT_TIME: Intl.DateTimeFormatOptions = {
  timeZone: TZ,
  hour: "2-digit",
  minute: "2-digit",
};

const OPT_DATETIME: Intl.DateTimeFormatOptions = {
  timeZone: TZ,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
};

/**
 * Formata um ISO datetime como data + hora em BRT.
 * Ex.: "06/08/2026, 19:15"
 */
export function fmtDateTime(iso: string | null | undefined, fallback = "—"): string {
  if (!iso) return fallback;
  try {
    return new Date(iso).toLocaleString("pt-BR", OPT_DATETIME);
  } catch {
    return fallback;
  }
}

/**
 * Formata um ISO datetime como apenas a data em BRT.
 * Ex.: "06/08/2026"
 */
export function fmtDateBRT(iso: string | null | undefined, fallback = "—"): string {
  if (!iso) return fallback;
  try {
    return new Date(iso).toLocaleDateString("pt-BR", OPT_DATE);
  } catch {
    return fallback;
  }
}

/**
 * Formata um ISO datetime como apenas o horário em BRT.
 * Ex.: "19:15"
 */
export function fmtTimeBRT(iso: string | null | undefined, fallback = "—"): string {
  if (!iso) return fallback;
  try {
    return new Date(iso).toLocaleTimeString("pt-BR", OPT_TIME);
  } catch {
    return fallback;
  }
}

/**
 * Formata um ISO datetime como "HH:mm de DD/MM" em BRT — para exibir
 * última sincronização, última varredura etc.
 * Ex.: "19:15 de 06/08"
 */
export function fmtLastSync(iso: string | null | undefined, fallback = "nunca"): string {
  if (!iso) return fallback;
  try {
    const d = new Date(iso);
    const time = d.toLocaleTimeString("pt-BR", OPT_TIME);
    const date = d.toLocaleDateString("pt-BR", { timeZone: TZ, day: "2-digit", month: "2-digit" });
    return `${time} de ${date}`;
  } catch {
    return fallback;
  }
}

/**
 * Returns true when `s` is a non-empty string that parses to a valid date.
 * Accepts ISO 8601 date-only ("YYYY-MM-DD") and datetime variants with or
 * without timezone offset (e.g. "2026-07-17T08:00:00Z").
 */
export function isValidIsoDate(s: string | null | undefined): boolean {
  if (!s) return false;
  const d = new Date(s.replace(/Z$/i, "+00:00"));
  return !isNaN(d.getTime());
}

// Maps Pydantic field names to Portuguese labels for user-facing messages.
const DATE_FIELD_LABELS: Record<string, string> = {
  licitacaoDataEncerramento: "Data de Encerramento",
  licitacaoDataAbertura:     "Data de Abertura",
  licitacaoDataPublicacao:   "Data de Publicação",
  prazo:                     "Prazo",
  dataEntrega:               "Data de Entrega",
};

/**
 * Parses a "DATE_INVALID:<label>:<value>" error message (thrown by the
 * client-side date validation in gerMutation) and returns the toast payload
 * that should be shown to the user, or null if the message is not a date
 * error.
 *
 * Keeping this as a pure function makes it straightforward to unit-test the
 * exact toast title/description without mounting any React component.
 */
export interface DateInvalidToast {
  title: string;
  description: string;
}

export function parseDateInvalidError(msg: string): DateInvalidToast | null {
  if (!msg.startsWith("DATE_INVALID:")) return null;
  const parts = msg.split(":");
  const label = parts[1] || "data";
  const value = parts.slice(2).join(":");
  return {
    title: "Formato de data inválido",
    description: `O valor "${value}" no campo "${label}" não está em um formato reconhecido. A licitação não pôde ser gerenciada.`,
  };
}

/**
 * Parses a FastAPI 422 response body and returns a Portuguese description for
 * the first date-related validation error found, or null if none is found.
 *
 * FastAPI/Pydantic 422 detail is an array of { loc, msg, type } objects.
 */
export function extract422DateMessage(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const { detail } = body as Record<string, unknown>;
  if (!Array.isArray(detail)) return null;

  for (const err of detail) {
    if (!err || typeof err !== "object") continue;
    const e = err as Record<string, unknown>;
    const msg = typeof e.msg === "string" ? e.msg.toLowerCase() : "";
    const loc = Array.isArray(e.loc) ? e.loc : [];
    const fieldName = loc[loc.length - 1];

    const isDateMsg =
      msg.includes("formato de data") ||
      msg.includes("iso 8601") ||
      msg.includes("date");
    const isDateField =
      typeof fieldName === "string" &&
      (fieldName.toLowerCase().includes("data") ||
       fieldName === "prazo" ||
       fieldName === "dataEntrega");

    if (isDateMsg || isDateField) {
      const label =
        typeof fieldName === "string"
          ? (DATE_FIELD_LABELS[fieldName] ?? fieldName)
          : "";
      return label
        ? `Formato de data inválido no campo "${label}". Use o formato AAAA-MM-DD.`
        : "Formato de data inválido. Use o formato AAAA-MM-DD.";
    }
  }
  return null;
}
