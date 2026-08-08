"""
Tests for ComprasNetScraper — covers request parameters, HTML parsing,
HTTP/network error handling, and the zero-result (JS-only) warning path.
"""
from __future__ import annotations

import logging
import pytest
import httpx
import respx

from collector.app.scrapers.comprasnet import ComprasNetScraper, BASE_URL, DETAIL_URL
from collector.app.config import CollectorSettings

# ── helpers ───────────────────────────────────────────────────────────────────

def _make_settings(**kwargs) -> CollectorSettings:
    defaults = dict(
        database_url="postgresql://test/test",
        playwright_timeout_ms=5_000,
        pncp_rate_limit_sleep=0,
    )
    defaults.update(kwargs)
    return CollectorSettings(**defaults)


_LISTING_HTML = """
<html><body>
<table>
  <tr><th>Número</th><th>Órgão</th><th>Objeto</th><th>Modalidade</th><th>Data</th><th>Situação</th></tr>
  <tr>
    <td>12345/2024</td>
    <td>Ministério X</td>
    <td>Aquisição de material</td>
    <td>Pregão Eletrônico</td>
    <td>01/01/2024</td>
    <td>Aberta</td>
  </tr>
  <tr>
    <td>67890/2024</td>
    <td>Secretaria Y</td>
    <td>Serviços de TI</td>
    <td>Pregão Eletrônico</td>
    <td>02/01/2024</td>
    <td>Encerrada</td>
  </tr>
</table>
</body></html>
"""

_JS_ONLY_HTML = """
<html><body>
<table>
  <tr><th>Número</th><th>Órgão</th></tr>
</table>
<script>carregarResultados();</script>
</body></html>
"""

_DETAIL_HTML = """
<html><body>
<p>UASG: 123456 Número Pregão 12345/2024</p>
<p>Objeto: Aquisição de material de escritório Modalidade: Pregão Situação: Aberta Abertura: 10/01/2024 Encerramento: fim</p>
</body></html>
"""

# ── scrape_by_date ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_scrape_by_date_parses_rows():
    """Should yield one dict per data row, correctly mapped to schema fields."""
    from datetime import date
    respx.get(BASE_URL).respond(200, text=_LISTING_HTML)

    scraper = ComprasNetScraper(_make_settings())
    await scraper.on_start()
    items = [item async for item in scraper.scrape_by_date(date(2024, 1, 1), date(2024, 1, 2))]
    await scraper.on_finish()

    assert len(items) == 2
    first = items[0]
    assert first["source"] == "comprasnet"
    assert first["external_id"] == "12345/2024"
    assert first["orgao"] == "Ministério X"
    assert first["objeto"] == "Aquisição de material"
    assert first["modalidade"] == "Pregão Eletrônico"
    assert first["data_publicacao"] == "01/01/2024"
    assert first["situacao"] == "Aberta"


@pytest.mark.asyncio
@respx.mock
async def test_scrape_by_date_sends_correct_params():
    """Request must include formatted start/end date params and submit=OK."""
    from datetime import date
    captured = {}

    def capture(request, *args, **kwargs):
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, text=_LISTING_HTML)

    respx.get(BASE_URL).mock(side_effect=capture)

    scraper = ComprasNetScraper(_make_settings())
    await scraper.on_start()
    _ = [item async for item in scraper.scrape_by_date(date(2024, 3, 15), date(2024, 3, 20))]
    await scraper.on_finish()

    assert captured["params"]["dt_publ_ini"] == "15/03/2024"
    assert captured["params"]["dt_publ_fim"] == "20/03/2024"
    assert captured["params"]["submit"] == "OK"


@pytest.mark.asyncio
@respx.mock
async def test_scrape_by_date_zero_results_logs_warning(caplog):
    """When HTML has no data rows (JS-only page), yield 0 items and log a warning."""
    from datetime import date
    respx.get(BASE_URL).respond(200, text=_JS_ONLY_HTML)

    scraper = ComprasNetScraper(_make_settings())
    await scraper.on_start()
    with caplog.at_level(logging.WARNING, logger="collector.comprasnet"):
        items = [item async for item in scraper.scrape_by_date(date(2024, 1, 1), date(2024, 1, 2))]
    await scraper.on_finish()

    assert items == []
    assert any("0 licitações" in r.message for r in caplog.records)


@pytest.mark.asyncio
@respx.mock
async def test_scrape_by_date_http_error_yields_nothing(caplog):
    """HTTP 500 should be caught; no items yielded; error logged."""
    from datetime import date
    respx.get(BASE_URL).respond(500)

    scraper = ComprasNetScraper(_make_settings())
    await scraper.on_start()
    with caplog.at_level(logging.ERROR, logger="collector.comprasnet"):
        items = [item async for item in scraper.scrape_by_date(date(2024, 1, 1), date(2024, 1, 2))]
    await scraper.on_finish()

    assert items == []
    assert any("HTTP" in r.message or "erro" in r.message.lower() for r in caplog.records)


@pytest.mark.asyncio
@respx.mock
async def test_scrape_by_date_network_error_yields_nothing(caplog):
    """Network-level errors (timeout, connection refused) should not propagate."""
    from datetime import date
    respx.get(BASE_URL).mock(side_effect=httpx.ConnectError("connection refused"))

    scraper = ComprasNetScraper(_make_settings())
    await scraper.on_start()
    with caplog.at_level(logging.ERROR, logger="collector.comprasnet"):
        items = [item async for item in scraper.scrape_by_date(date(2024, 1, 1), date(2024, 1, 2))]
    await scraper.on_finish()

    assert items == []
    assert any("rede" in r.message.lower() or "network" in r.message.lower() or "connection" in r.message.lower()
               for r in caplog.records)


# ── scrape_by_id ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_scrape_by_id_parses_detail():
    """Should extract fields from detail page HTML."""
    respx.get(DETAIL_URL).respond(200, text=_DETAIL_HTML)

    scraper = ComprasNetScraper(_make_settings())
    await scraper.on_start()
    result = await scraper.scrape_by_id("12345/2024")
    await scraper.on_finish()

    assert result is not None
    assert result["source"] == "comprasnet"
    assert result["external_id"] == "12345/2024"
    assert "escritório" in result["objeto"]


@pytest.mark.asyncio
@respx.mock
async def test_scrape_by_id_http_error_returns_none(caplog):
    """HTTP error on detail page should return None without raising."""
    respx.get(DETAIL_URL).respond(404)

    scraper = ComprasNetScraper(_make_settings())
    await scraper.on_start()
    with caplog.at_level(logging.ERROR, logger="collector.comprasnet"):
        result = await scraper.scrape_by_id("99999/2024")
    await scraper.on_finish()

    assert result is None
    assert any("HTTP" in r.message or "erro" in r.message.lower() for r in caplog.records)


@pytest.mark.asyncio
@respx.mock
async def test_scrape_by_id_network_error_returns_none(caplog):
    """Network error on detail page should return None without raising."""
    respx.get(DETAIL_URL).mock(side_effect=httpx.TimeoutException("timed out"))

    scraper = ComprasNetScraper(_make_settings())
    await scraper.on_start()
    with caplog.at_level(logging.ERROR, logger="collector.comprasnet"):
        result = await scraper.scrape_by_id("99999/2024")
    await scraper.on_finish()

    assert result is None


# ── Accept-Encoding compatibility ─────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_no_brotli_in_accept_encoding():
    """Client must not advertise Brotli encoding — httpx cannot decode it without extras."""
    from datetime import date
    sent_headers: dict = {}

    def capture(request, *args, **kwargs):
        sent_headers.update(dict(request.headers))
        return httpx.Response(200, text=_LISTING_HTML)

    respx.get(BASE_URL).mock(side_effect=capture)

    scraper = ComprasNetScraper(_make_settings())
    await scraper.on_start()
    _ = [item async for item in scraper.scrape_by_date(date(2024, 1, 1), date(2024, 1, 2))]
    await scraper.on_finish()

    accept_enc = sent_headers.get("accept-encoding", "")
    assert "br" not in accept_enc.split(",")
