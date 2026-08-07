"""
ComprasNetScraper — Portal ComprasNet (www.comprasnet.gov.br)
Usa Playwright para renderizar JS + BeautifulSoup para parse de HTML.

O portal exige navegação headless pois usa JS pesado para renderizar resultados.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import AsyncIterator, Optional

from bs4 import BeautifulSoup

from ..base_scraper import BaseScraper
from ..config import CollectorSettings

logger = logging.getLogger("collector.comprasnet")

BASE_URL = "https://www.comprasnet.gov.br/ConsultaLicitacoes/ConsLicitacao_Relacao.asp"


class ComprasNetScraper(BaseScraper):
    SOURCE = "comprasnet"

    def __init__(self, settings: Optional[CollectorSettings] = None):
        super().__init__(settings)
        self._playwright = None
        self._browser = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def on_start(self) -> None:
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.settings.headless,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        logger.info("ComprasNet: browser iniciado.")

    async def on_finish(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("ComprasNet: browser encerrado.")

    # ── scrape_by_date ────────────────────────────────────────────────────────

    async def scrape_by_date(self, start: date, end: date) -> AsyncIterator[dict]:
        if not self._browser:
            await self.on_start()

        page = await self._browser.new_page()
        page.set_default_timeout(self.settings.playwright_timeout_ms)

        try:
            url = (
                f"{BASE_URL}"
                f"?numprp=&objeto=&dt_publ_ini={start.strftime('%d%%2F%m%%2F%Y')}"
                f"&dt_publ_fim={end.strftime('%d%%2F%m%%2F%Y')}"
                f"&chkmodalidade=on&coduasg=&Uf=&municipio=&situacao=&submit=OK"
            )
            logger.info("ComprasNet: %s", url)
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(2000)

            html = await page.content()
            items = self._parse_listing(html)
            logger.info("ComprasNet: %d licitações encontradas.", len(items))

            for item in items:
                yield item
                await asyncio.sleep(self.settings.pncp_rate_limit_sleep)

        except Exception as exc:
            logger.error("ComprasNet scrape_by_date: %s", exc)
        finally:
            await page.close()

    # ── scrape_by_id ──────────────────────────────────────────────────────────

    async def scrape_by_id(self, external_id: str) -> dict | None:
        if not self._browser:
            await self.on_start()

        page = await self._browser.new_page()
        page.set_default_timeout(self.settings.playwright_timeout_ms)

        try:
            url = f"https://www.comprasnet.gov.br/ConsultaLicitacoes/download/download_editais_detalhe.asp?coduasg=&numprp={external_id}"
            await page.goto(url, wait_until="networkidle")
            html = await page.content()
            return self._parse_detail(html, external_id)
        except Exception as exc:
            logger.error("ComprasNet scrape_by_id(%s): %s", external_id, exc)
            return None
        finally:
            await page.close()

    # ── Parsers ───────────────────────────────────────────────────────────────

    def _parse_listing(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # ComprasNet usa tabelas para listagem
        for row in soup.select("table tr"):
            cells = row.find_all("td")
            if len(cells) < 6:
                continue
            texts = [c.get_text(strip=True) for c in cells]
            # Heurística: primeira célula com número de pregão
            if not texts[0] or not any(c.isdigit() for c in texts[0]):
                continue

            results.append({
                "source":           self.SOURCE,
                "external_id":      self._normalize_str(texts[0]),
                "numero_controle":  self._normalize_str(texts[0]),
                "objeto":           self._normalize_str(texts[2]) if len(texts) > 2 else "",
                "orgao":            self._normalize_str(texts[1]) if len(texts) > 1 else "",
                "cnpj_orgao":       None,
                "unidade":          "",
                "uf":               None,
                "municipio":        None,
                "modalidade":       self._normalize_str(texts[3]) if len(texts) > 3 else "",
                "situacao":         self._normalize_str(texts[5]) if len(texts) > 5 else "",
                "valor_estimado":   None,
                "data_publicacao":  self._normalize_str(texts[4]) if len(texts) > 4 else "",
                "data_abertura":    "",
                "data_encerramento": "",
                "srp":              False,
                "link_original":    "",
                "dados_brutos":     {"raw_cells": texts},
                "items":            [],
            })

        return results

    def _parse_detail(self, html: str, external_id: str) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        if not text:
            return None

        return {
            "source":           self.SOURCE,
            "external_id":      external_id,
            "numero_controle":  external_id,
            "objeto":           self._extract_between(text, "Objeto:", "Modalidade:"),
            "orgao":            self._extract_between(text, "UASG:", "Número"),
            "cnpj_orgao":       None,
            "unidade":          "",
            "uf":               None,
            "municipio":        None,
            "modalidade":       self._extract_between(text, "Modalidade:", "Situação:"),
            "situacao":         self._extract_between(text, "Situação:", "Abertura:"),
            "valor_estimado":   None,
            "data_publicacao":  "",
            "data_abertura":    self._extract_between(text, "Abertura:", "Encerramento:"),
            "data_encerramento": "",
            "srp":              False,
            "link_original":    "",
            "dados_brutos":     {"html_snippet": text[:2000]},
            "items":            [],
        }

    def _extract_between(self, text: str, start_kw: str, end_kw: str) -> str:
        try:
            s = text.index(start_kw) + len(start_kw)
            e = text.index(end_kw, s)
            return self._normalize_str(text[s:e])
        except ValueError:
            return ""
