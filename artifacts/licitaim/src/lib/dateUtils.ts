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
