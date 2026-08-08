"""
ComprasNetScraper — Portal ComprasNet (www.comprasnet.gov.br)
Usa httpx + BeautifulSoup para scraping sem dependência de browser headless.

Se o portal bloquear o acesso direto (JS pesado não executado), a listagem
retornará 0 resultados e um aviso será logado — sem falha silenciosa.
O BBMNetScraper ainda usa Playwright; a dependência permanece no projeto
enquanto aquele scraper não for migrado.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import AsyncIterator, Optional

import httpx
from bs4 import BeautifulSoup

from ..base_scraper import BaseScraper
from ..config import CollectorSettings

logger = logging.getLogger("collector.comprasnet")

BASE_URL = "https://www.comprasnet.gov.br/ConsultaLicitacoes/ConsLicitacao_Relacao.asp"
DETAIL_URL = "https://www.comprasnet.gov.br/ConsultaLicitacoes/download/download_editais_detalhe.asp"

# Headers that mimic a real browser to reduce the chance of being blocked
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}


class ComprasNetScraper(BaseScraper):
    SOURCE = "comprasnet"

    def __init__(self, settings: Optional[CollectorSettings] = None):
        super().__init__(settings)
        self._client: Optional[httpx.AsyncClient] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def on_start(self) -> None:
        timeout = httpx.Timeout(
            connect=10.0,
            read=self.settings.playwright_timeout_ms / 1000,
            write=10.0,
            pool=10.0,
        )
        self._client = httpx.AsyncClient(
            headers=_HEADERS,
            timeout=timeout,
            follow_redirects=True,
        )
        logger.info("ComprasNet: cliente HTTP iniciado.")

    async def on_finish(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("ComprasNet: cliente HTTP encerrado.")

    # ── scrape_by_date ────────────────────────────────────────────────────────

    async def scrape_by_date(self, start: date, end: date) -> AsyncIterator[dict]:
        if self._client is None:
            await self.on_start()

        params = {
            "numprp": "",
            "objeto": "",
            "dt_publ_ini": start.strftime("%d/%m/%Y"),
            "dt_publ_fim": end.strftime("%d/%m/%Y"),
            "chkmodalidade": "on",
            "coduasg": "",
            "Uf": "",
            "municipio": "",
            "situacao": "",
            "submit": "OK",
        }

        try:
            logger.info("ComprasNet: consultando %s → %s", start, end)
            response = await self._client.get(BASE_URL, params=params)
            response.raise_for_status()

            items = self._parse_listing(response.text)

            if not items:
                # Could be JS-rendered content that httpx cannot execute
                logger.warning(
                    "ComprasNet: 0 licitações encontradas para %s–%s. "
                    "O portal pode estar usando JS pesado que não pode ser executado "
                    "sem browser headless, ou simplesmente não há resultados no período.",
                    start,
                    end,
                )
            else:
                logger.info("ComprasNet: %d licitações encontradas.", len(items))

            for item in items:
                yield item
                await asyncio.sleep(self.settings.pncp_rate_limit_sleep)

        except httpx.HTTPStatusError as exc:
            logger.error(
                "ComprasNet scrape_by_date: HTTP %s — %s",
                exc.response.status_code,
                exc,
            )
        except httpx.RequestError as exc:
            logger.error("ComprasNet scrape_by_date: erro de rede — %s", exc)
        except Exception as exc:
            logger.error("ComprasNet scrape_by_date: erro inesperado — %s", exc)

    # ── scrape_by_id ──────────────────────────────────────────────────────────

    async def scrape_by_id(self, external_id: str) -> dict | None:
        if self._client is None:
            await self.on_start()

        params = {"coduasg": "", "numprp": external_id}

        try:
            response = await self._client.get(DETAIL_URL, params=params)
            response.raise_for_status()
            return self._parse_detail(response.text, external_id)
        except httpx.HTTPStatusError as exc:
            logger.error(
                "ComprasNet scrape_by_id(%s): HTTP %s — %s",
                external_id,
                exc.response.status_code,
                exc,
            )
            return None
        except httpx.RequestError as exc:
            logger.error(
                "ComprasNet scrape_by_id(%s): erro de rede — %s", external_id, exc
            )
            return None
        except Exception as exc:
            logger.error(
                "ComprasNet scrape_by_id(%s): erro inesperado — %s", external_id, exc
            )
            return None

    # ── Parsers ───────────────────────────────────────────────────────────────

    def _parse_listing(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # ComprasNet uses tables for listing results
        for row in soup.select("table tr"):
            cells = row.find_all("td")
            if len(cells) < 6:
                continue
            texts = [c.get_text(strip=True) for c in cells]
            # Heuristic: first cell should contain a tender number (has digits)
            if not texts[0] or not any(c.isdigit() for c in texts[0]):
                continue

            results.append({
                "source":            self.SOURCE,
                "external_id":       self._normalize_str(texts[0]),
                "numero_controle":   self._normalize_str(texts[0]),
                "objeto":            self._normalize_str(texts[2]) if len(texts) > 2 else "",
                "orgao":             self._normalize_str(texts[1]) if len(texts) > 1 else "",
                "cnpj_orgao":        None,
                "unidade":           "",
                "uf":                None,
                "municipio":         None,
                "modalidade":        self._normalize_str(texts[3]) if len(texts) > 3 else "",
                "situacao":          self._normalize_str(texts[5]) if len(texts) > 5 else "",
                "valor_estimado":    None,
                "data_publicacao":   self._normalize_str(texts[4]) if len(texts) > 4 else "",
                "data_abertura":     "",
                "data_encerramento": "",
                "srp":               False,
                "link_original":     "",
                "dados_brutos":      {"raw_cells": texts},
                "items":             [],
            })

        return results

    def _parse_detail(self, html: str, external_id: str) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        if not text:
            return None

        return {
            "source":            self.SOURCE,
            "external_id":       external_id,
            "numero_controle":   external_id,
            "objeto":            self._extract_between(text, "Objeto:", "Modalidade:"),
            "orgao":             self._extract_between(text, "UASG:", "Número"),
            "cnpj_orgao":        None,
            "unidade":           "",
            "uf":                None,
            "municipio":         None,
            "modalidade":        self._extract_between(text, "Modalidade:", "Situação:"),
            "situacao":          self._extract_between(text, "Situação:", "Abertura:"),
            "valor_estimado":    None,
            "data_publicacao":   "",
            "data_abertura":     self._extract_between(text, "Abertura:", "Encerramento:"),
            "data_encerramento": "",
            "srp":               False,
            "link_original":     "",
            "dados_brutos":      {"html_snippet": text[:2000]},
            "items":             [],
        }

    def _extract_between(self, text: str, start_kw: str, end_kw: str) -> str:
        try:
            s = text.index(start_kw) + len(start_kw)
            e = text.index(end_kw, s)
            return self._normalize_str(text[s:e])
        except ValueError:
            return ""
