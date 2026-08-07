"""
BECSPScraper — Bolsa Eletrônica de Compras do Estado de São Paulo
  https://www.bec.sp.gov.br

Usa httpx (sem JS) + BeautifulSoup, pois o portal tem páginas server-side rendering.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import AsyncIterator, Optional

import httpx
from bs4 import BeautifulSoup
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from ..base_scraper import BaseScraper
from ..config import CollectorSettings

logger = logging.getLogger("collector.bec_sp")

BASE_URL = "https://www.bec.sp.gov.br"
SEARCH_PATH = "/Publicacoes/ui/PublicacaoOFCompraElectronica.aspx"


class BECSPScraper(BaseScraper):
    SOURCE = "bec_sp"

    def __init__(self, settings: Optional[CollectorSettings] = None):
        super().__init__(settings)
        self._client: Optional[httpx.AsyncClient] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def on_start(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                "User-Agent": "Mozilla/5.0 LicitAIM-Collector/1.0",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "pt-BR,pt;q=0.9",
            },
            follow_redirects=True,
        )
        logger.info("BEC-SP: cliente httpx iniciado.")

    async def on_finish(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("BEC-SP: cliente encerrado.")

    # ── scrape_by_date ────────────────────────────────────────────────────────

    async def scrape_by_date(self, start: date, end: date) -> AsyncIterator[dict]:
        if not self._client:
            await self.on_start()

        pagina = 1
        has_more = True

        while has_more:
            params = {
                "dtIni": start.strftime("%d/%m/%Y"),
                "dtFim": end.strftime("%d/%m/%Y"),
                "pagina": str(pagina),
            }
            try:
                html = await self._get_with_retry(SEARCH_PATH, params)
            except Exception as exc:
                logger.error("BEC-SP página %d falhou: %s", pagina, exc)
                break

            items, has_more = self._parse_listing(html)
            logger.info("BEC-SP página %d — %d itens, has_more=%s", pagina, len(items), has_more)

            for item in items:
                yield item

            pagina += 1
            await asyncio.sleep(self.settings.pncp_rate_limit_sleep)

    # ── scrape_by_id ──────────────────────────────────────────────────────────

    async def scrape_by_id(self, external_id: str) -> dict | None:
        if not self._client:
            await self.on_start()
        try:
            html = await self._get_with_retry(
                f"/Publicacoes/ui/detalhe.aspx",
                {"id": external_id},
            )
            return self._parse_detail(html, external_id)
        except Exception as exc:
            logger.error("BEC-SP scrape_by_id(%s): %s", external_id, exc)
            return None

    # ── HTTP ──────────────────────────────────────────────────────────────────

    async def _get_with_retry(self, path: str, params: dict) -> str:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
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
                resp.raise_for_status()
                return resp.text

    # ── Parsers ───────────────────────────────────────────────────────────────

    def _parse_listing(self, html: str) -> tuple[list[dict], bool]:
        soup = BeautifulSoup(html, "html.parser")
        results = []

        for row in soup.select("table.resultado tr, table#dgOferta tr"):
            cells = row.find_all("td")
            if len(cells) < 5:
                continue
            texts = [c.get_text(strip=True) for c in cells]

            ext_id = self._normalize_str(texts[0])
            if not ext_id or not any(c.isdigit() for c in ext_id):
                continue

            results.append({
                "source":           self.SOURCE,
                "external_id":      ext_id,
                "numero_controle":  ext_id,
                "objeto":           self._normalize_str(texts[2]) if len(texts) > 2 else "",
                "orgao":            self._normalize_str(texts[1]) if len(texts) > 1 else "",
                "cnpj_orgao":       None,
                "unidade":          "",
                "uf":               "SP",
                "municipio":        None,
                "modalidade":       "pregao_eletronico",
                "situacao":         self._normalize_str(texts[4]) if len(texts) > 4 else "",
                "valor_estimado":   self._safe_float(texts[3]) if len(texts) > 3 else None,
                "data_publicacao":  "",
                "data_abertura":    "",
                "data_encerramento": "",
                "srp":              False,
                "link_original":    f"{BASE_URL}/Publicacoes/ui/detalhe.aspx?id={ext_id}",
                "dados_brutos":     {"raw_cells": texts},
                "items":            [],
            })

        # Detecta paginação "próxima página"
        has_more = bool(soup.select_one("a[href*='proxima'], .next-page, [id*='lnkProximo']"))
        return results, has_more

    def _parse_detail(self, html: str, external_id: str) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")

        def _field(label: str) -> str:
            tag = soup.find(string=lambda t: t and label.lower() in t.lower())
            if tag and tag.parent and tag.parent.find_next_sibling():
                return self._normalize_str(tag.parent.find_next_sibling().get_text())
            return ""

        return {
            "source":           self.SOURCE,
            "external_id":      external_id,
            "numero_controle":  external_id,
            "objeto":           _field("Objeto"),
            "orgao":            _field("Órgão"),
            "cnpj_orgao":       None,
            "unidade":          _field("Unidade"),
            "uf":               "SP",
            "municipio":        None,
            "modalidade":       "pregao_eletronico",
            "situacao":         _field("Situação"),
            "valor_estimado":   self._safe_float(_field("Valor")),
            "data_publicacao":  _field("Publicação"),
            "data_abertura":    _field("Abertura"),
            "data_encerramento": _field("Encerramento"),
            "srp":              False,
            "link_original":    f"{BASE_URL}/Publicacoes/ui/detalhe.aspx?id={external_id}",
            "dados_brutos":     {"html_snippet": soup.get_text()[:2000]},
            "items":            [],
        }
