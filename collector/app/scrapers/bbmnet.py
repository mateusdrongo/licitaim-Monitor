"""
BBMNetScraper — BBMNet Licitações (www.bbmnet.com.br)
Usa Playwright (portal com JS pesado) para navegação e extração.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import AsyncIterator, Optional

from bs4 import BeautifulSoup

from ..base_scraper import BaseScraper
from ..config import CollectorSettings

logger = logging.getLogger("collector.bbmnet")

BASE_URL = "https://www.bbmnet.com.br"
SEARCH_URL = f"{BASE_URL}/licitacoes"


class BBMNetScraper(BaseScraper):
    SOURCE = "bbmnet"

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
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"],
        )
        logger.info("BBMNet: browser iniciado.")

    async def on_finish(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("BBMNet: browser encerrado.")

    # ── scrape_by_date ────────────────────────────────────────────────────────

    async def scrape_by_date(self, start: date, end: date) -> AsyncIterator[dict]:
        if not self._browser:
            await self.on_start()

        page = await self._browser.new_page()
        page.set_default_timeout(self.settings.playwright_timeout_ms)

        try:
            await page.goto(SEARCH_URL, wait_until="networkidle")
            await page.wait_for_timeout(2000)

            # Preenche filtro de datas se disponível
            try:
                await page.fill("input[name*='dataIni'], input[placeholder*='Data inicial']",
                                start.strftime("%d/%m/%Y"))
                await page.fill("input[name*='dataFim'], input[placeholder*='Data final']",
                                end.strftime("%d/%m/%Y"))
                await page.click("button[type='submit'], input[type='submit']")
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)
            except Exception:
                pass  # Portal pode não ter filtro de datas visível

            pagina = 1
            while True:
                html = await page.content()
                items = self._parse_listing(html)
                logger.info("BBMNet página %d — %d itens.", pagina, len(items))

                for item in items:
                    yield item

                # Tenta navegar para próxima página
                try:
                    next_btn = page.locator("a.next, button.next, a[aria-label='Próxima']").first
                    is_disabled = await next_btn.get_attribute("disabled")
                    if is_disabled or not await next_btn.is_visible():
                        break
                    await next_btn.click()
                    await page.wait_for_load_state("networkidle")
                    await page.wait_for_timeout(1500)
                    pagina += 1
                    await asyncio.sleep(self.settings.pncp_rate_limit_sleep)
                except Exception:
                    break

        except Exception as exc:
            logger.error("BBMNet scrape_by_date: %s", exc)
        finally:
            await page.close()

    # ── scrape_by_id ──────────────────────────────────────────────────────────

    async def scrape_by_id(self, external_id: str) -> dict | None:
        if not self._browser:
            await self.on_start()

        page = await self._browser.new_page()
        page.set_default_timeout(self.settings.playwright_timeout_ms)

        try:
            url = f"{BASE_URL}/licitacoes/{external_id}"
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(2000)
            html = await page.content()
            return self._parse_detail(html, external_id)
        except Exception as exc:
            logger.error("BBMNet scrape_by_id(%s): %s", external_id, exc)
            return None
        finally:
            await page.close()

    # ── Parsers ───────────────────────────────────────────────────────────────

    def _parse_listing(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        results = []

        selectors = [
            "table.licitacoes tr",
            "div.licitacao-item",
            "article.card-licitacao",
            "tr[data-id]",
        ]

        rows = []
        for sel in selectors:
            rows = soup.select(sel)
            if rows:
                break

        for row in rows:
            cells = row.find_all(["td", "div", "span"])
            if len(cells) < 3:
                continue
            texts = [c.get_text(strip=True) for c in cells]

            # Tenta extrair ID do atributo data-id ou href
            ext_id = (
                row.get("data-id")
                or row.get("id")
                or self._normalize_str(texts[0])
            )
            if not ext_id:
                continue

            results.append({
                "source":           self.SOURCE,
                "external_id":      str(ext_id),
                "numero_controle":  str(ext_id),
                "objeto":           self._normalize_str(texts[1]) if len(texts) > 1 else "",
                "orgao":            self._normalize_str(texts[2]) if len(texts) > 2 else "",
                "cnpj_orgao":       None,
                "unidade":          "",
                "uf":               None,
                "municipio":        None,
                "modalidade":       "",
                "situacao":         self._normalize_str(texts[-1]) if texts else "",
                "valor_estimado":   None,
                "data_publicacao":  "",
                "data_abertura":    "",
                "data_encerramento": "",
                "srp":              False,
                "link_original":    f"{BASE_URL}/licitacoes/{ext_id}",
                "dados_brutos":     {"raw_texts": texts},
                "items":            [],
            })

        return results

    def _parse_detail(self, html: str, external_id: str) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")

        def _field(*labels: str) -> str:
            for label in labels:
                tag = soup.find(string=lambda t, l=label: t and l.lower() in t.lower())
                if tag:
                    parent = tag.parent
                    sibling = parent.find_next_sibling() if parent else None
                    if sibling:
                        return self._normalize_str(sibling.get_text())
            return ""

        return {
            "source":           self.SOURCE,
            "external_id":      external_id,
            "numero_controle":  external_id,
            "objeto":           _field("Objeto", "Descrição"),
            "orgao":            _field("Órgão", "Entidade"),
            "cnpj_orgao":       None,
            "unidade":          _field("Unidade"),
            "uf":               _field("UF", "Estado"),
            "municipio":        _field("Município", "Cidade"),
            "modalidade":       _field("Modalidade"),
            "situacao":         _field("Situação", "Status"),
            "valor_estimado":   self._safe_float(_field("Valor estimado", "Valor")),
            "data_publicacao":  _field("Publicação", "Data publicação"),
            "data_abertura":    _field("Abertura"),
            "data_encerramento": _field("Encerramento"),
            "srp":              "srp" in soup.get_text().lower(),
            "link_original":    f"{BASE_URL}/licitacoes/{external_id}",
            "dados_brutos":     {"html_snippet": soup.get_text()[:3000]},
            "items":            [],
        }
