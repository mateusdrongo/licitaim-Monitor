"""
PNCPScraper — API oficial PNCP
  GET https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao

Mapeamentos de código:
  Modalidade: conforme tabela oficial PNCP (codigoModalidadeContratacao)
  Situação:   1=Divulgada, 2=Retificada, 3=Suspensa, ...

Rate limiting: sleep entre requests configurável (config.pncp_rate_limit_sleep).
Retry: tenacity com backoff exponencial em 5xx / timeout.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import AsyncIterator, Optional

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from ..base_scraper import BaseScraper
from ..config import CollectorSettings

logger = logging.getLogger("collector.pncp")

# ── Mapeamentos de código PNCP ────────────────────────────────────────────────

MODALIDADE_MAP: dict[int, str] = {
    1:  "leilao_eletronico",
    2:  "dialogo_competitivo",
    3:  "concurso",
    4:  "concorrencia_eletronica",
    5:  "concorrencia_presencial",
    6:  "pregao_eletronico",
    7:  "pregao_presencial",
    8:  "dispensa",
    9:  "inexigibilidade",
    10: "manifestacao_interesse",
    11: "pre_qualificacao",
    12: "credenciamento",
    13: "leilao_presencial",
    14: "inaplicabilidade_licitacao",
    15: "chamada_publica",
    16: "concorrencia_eletronica_internacional",
    17: "concorrencia_presencial_internacional",
    18: "pregao_eletronico_internacional",
    19: "pregao_presencial_internacional",
}

# Nome legível por código — usado para exibição
MODALIDADE_LABEL: dict[int, str] = {
    1:  "Leilão - Eletrônico",
    2:  "Diálogo Competitivo",
    3:  "Concurso",
    4:  "Concorrência - Eletrônica",
    5:  "Concorrência - Presencial",
    6:  "Pregão - Eletrônico",
    7:  "Pregão - Presencial",
    8:  "Dispensa",
    9:  "Inexigibilidade",
    10: "Manifestação de Interesse",
    11: "Pré-qualificação",
    12: "Credenciamento",
    13: "Leilão - Presencial",
    14: "Inaplicabilidade da Licitação",
    15: "Chamada Pública",
    16: "Concorrência – Eletrônica Internacional",
    17: "Concorrência – Presencial Internacional",
    18: "Pregão – Eletrônico Internacional",
    19: "Pregão – Presencial Internacional",
}

SITUACAO_MAP: dict[int, str] = {
    1: "divulgada",
    2: "retificada",
    3: "suspensa",
    4: "cancelada",
    5: "homologada",
    6: "fracassada",
    7: "deserta",
    8: "anulada",
    9: "revogada",
}

RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, RETRYABLE_EXCEPTIONS):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


class PNCPScraper(BaseScraper):
    SOURCE = "pncp"

    def __init__(self, settings: Optional[CollectorSettings] = None):
        super().__init__(settings)
        self._client: Optional[httpx.AsyncClient] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def on_start(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self.settings.pncp_base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                "User-Agent": "LicitAIM-Collector/1.0 (contato@licitaim.com.br)",
                "Accept": "application/json",
            },
            follow_redirects=True,
        )

    async def on_finish(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── scrape_by_date ────────────────────────────────────────────────────────

    async def scrape_by_date(self, start: date, end: date) -> AsyncIterator[dict]:
        if not self._client:
            await self.on_start()

        date_str_start = start.strftime("%Y%m%d")
        date_str_end = end.strftime("%Y%m%d")
        pagina = 1
        total_pages = 1  # atualizado na primeira resposta

        logger.info("PNCP scraping %s → %s", date_str_start, date_str_end)

        while pagina <= min(total_pages, self.settings.pncp_max_pages):
            params = {
                "dataInicial": date_str_start,
                "dataFinal": date_str_end,
                "pagina": pagina,
                "tamanhoPagina": self.settings.pncp_page_size,
            }

            try:
                data = await self._get_with_retry("/contratacoes/publicacao", params)
            except Exception as exc:
                logger.error("PNCP página %d falhou definitivamente: %s", pagina, exc)
                break

            items = data.get("data") or []
            if not items:
                logger.info("PNCP página %d vazia — encerrando.", pagina)
                break

            # Atualiza total de páginas a partir da resposta
            total_registros = data.get("totalRegistros") or data.get("total", 0)
            if total_registros:
                import math
                total_pages = math.ceil(total_registros / self.settings.pncp_page_size)

            logger.info(
                "PNCP página %d/%d — %d registros",
                pagina, total_pages, len(items),
            )

            for item in items:
                yield self._map_tender(item)

            pagina += 1
            await asyncio.sleep(self.settings.pncp_rate_limit_sleep)

    # ── scrape_by_id ──────────────────────────────────────────────────────────

    async def scrape_by_id(self, external_id: str) -> dict | None:
        """
        external_id esperado: "<cnpj>/<ano>/<sequencial>"
        ex: "00394460000154/2024/1"
        """
        if not self._client:
            await self.on_start()

        parts = external_id.replace("-", "/").split("/")
        if len(parts) < 3:
            logger.warning("PNCP external_id inválido: %s", external_id)
            return None

        cnpj, ano, seq = parts[0], parts[1], parts[2]
        path = f"/orgaos/{cnpj}/compras/{ano}/{seq}"

        try:
            data = await self._get_with_retry(path, {})
        except Exception as exc:
            logger.error("PNCP scrape_by_id(%s): %s", external_id, exc)
            return None

        return self._map_tender(data)

    # ── HTTP com retry ────────────────────────────────────────────────────────

    async def _get_with_retry(self, path: str, params: dict) -> dict:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(tuple(list(RETRYABLE_EXCEPTIONS) + [httpx.HTTPStatusError])),
            stop=stop_after_attempt(self.settings.retry_attempts),
            wait=wait_exponential(
                min=self.settings.retry_min_wait,
                max=self.settings.retry_max_wait,
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                resp = await self._client.get(path, params=params)
                if resp.status_code == 404:
                    return {}
                resp.raise_for_status()
                return resp.json()

    # ── Mapeamento ────────────────────────────────────────────────────────────

    def _map_tender(self, raw: dict) -> dict:
        orgao    = raw.get("orgaoEntidade") or {}
        unidade  = raw.get("unidadeOrgao") or {}
        am_code  = raw.get("codigoModalidadeContratacao") or raw.get("modalidadeCodigo")
        sit_code = raw.get("codigoSituacaoEdital") or raw.get("situacaoCodigo")
        ext_id   = (
            raw.get("numeroControlePNCP")
            or f"{orgao.get('cnpj','')}/{raw.get('anoCompra','')}/{raw.get('sequencialCompra','')}"
        )

        # Itens (se já vieram no payload)
        raw_items = raw.get("itens") or []
        items = [self._map_item(it) for it in raw_items]

        return {
            "source":           self.SOURCE,
            "external_id":      self._normalize_str(ext_id),
            "numero_controle":  self._normalize_str(raw.get("numeroControlePNCP")),
            "objeto":           self._normalize_str(raw.get("objetoCompra")),
            "orgao":            self._normalize_str(orgao.get("razaoSocial")),
            "cnpj_orgao":       self._clean_cnpj(orgao.get("cnpj")),
            "unidade":          self._normalize_str(unidade.get("nomeUnidade")),
            "uf":               self._normalize_str(unidade.get("ufSigla") or unidade.get("ufNome", "")[:2]).upper() or None,
            "municipio":        self._normalize_str(unidade.get("municipioNome")),
            "modalidade":       MODALIDADE_MAP.get(am_code) or self._normalize_str(raw.get("modalidadeNome")),
            "modalidade_codigo": am_code,
            "situacao":         SITUACAO_MAP.get(sit_code) or self._normalize_str(raw.get("situacaoCompraNome")),
            "situacao_codigo":  sit_code,
            "valor_estimado":   self._safe_float(raw.get("valorTotalEstimado")),
            "data_publicacao":  self._normalize_str(raw.get("dataPublicacaoPncp")),
            "data_abertura":    self._normalize_str(raw.get("dataAberturaProposta")),
            "data_encerramento": self._normalize_str(raw.get("dataEncerramentoProposta")),
            "srp":              bool(raw.get("srp", False)),
            "link_original":    self._normalize_str(raw.get("linkSistemaOrigem")),
            "dados_brutos":     raw,
            "items":            items,
        }

    def _map_item(self, raw: dict) -> dict:
        return {
            "numero_item":   self._safe_int(raw.get("numeroItem")),
            "descricao":     self._normalize_str(raw.get("descricao")),
            "quantidade":    self._safe_float(raw.get("quantidade")),
            "unidade_medida": self._normalize_str(raw.get("unidadeMedida")),
            "valor_unitario": self._safe_float(raw.get("valorUnitarioEstimado")),
            "valor_total":   self._safe_float(raw.get("valorTotal")),
        }

    def _clean_cnpj(self, val: object) -> str | None:
        if not val:
            return None
        digits = "".join(c for c in str(val) if c.isdigit())
        return digits if len(digits) in (11, 14) else self._normalize_str(val)
