#!/usr/bin/env python3
"""
standalone.py — Collector standalone sem Redis/Celery/RabbitMQ.

Executa scraping periódico do PNCP, ComprasNet e BEC-SP usando asyncio puro.
Pode ser iniciado como workflow independente:
    python -m collector.app.standalone

Variáveis de ambiente:
    DATABASE_URL                 — PostgreSQL connection string (obrigatória)
    COLLECTOR_INTERVAL_HOURS     — Intervalo entre ciclos (padrão: 4)
    COLLECTOR_DAYS               — Janela de dias para trás (padrão: 1)
    LOG_LEVEL                    — Nível de log (padrão: INFO)
    COLLECTOR_SKIP_COMPRASNET    — Se "1", pula scraping ComprasNet (padrão: 0)
    COLLECTOR_SKIP_BEC_SP        — Se "1", pula scraping BEC-SP (padrão: 0)
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import date, timedelta
from typing import Optional

# Garante que o pacote collector/ está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("collector.standalone")

INTERVAL_HOURS = int(os.environ.get("COLLECTOR_INTERVAL_HOURS", "4"))
SCRAPE_DAYS    = int(os.environ.get("COLLECTOR_DAYS", "1"))


# ── Processor sem broker ───────────────────────────────────────────────────────

class StandaloneTenderProcessor:
    """
    Wrapper sobre TenderProcessor que desabilita completamente a publicação
    em RabbitMQ/Elasticsearch. Evita qualquer import de aio-pika ou celery
    no caminho de execução standalone.
    """

    def __init__(self, pool) -> None:
        from .processors.tender_processor import TenderProcessor
        self._processor = TenderProcessor(pool)

        # Substitui o método de publicação por um no-op antes de qualquer uso
        async def _noop_publish(tender_id: str, tender: dict) -> None:
            pass  # ES sync via broker não está disponível no modo standalone

        self._processor._publish_es_event = _noop_publish  # type: ignore[assignment]

    async def process(self, tender: dict) -> Optional[str]:
        return await self._processor.process(tender)


# ── Schema ────────────────────────────────────────────────────────────────────

async def apply_schema(db_url: str) -> None:
    """Cria as tabelas tenders/tender_items/tender_history se não existirem."""
    import asyncpg

    schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")
    if not os.path.exists(schema_path):
        logger.warning("schema.sql não encontrado em %s", schema_path)
        return

    with open(schema_path) as f:
        sql = f.read()

    pool = await asyncpg.create_pool(db_url)
    try:
        await pool.execute(sql)
        logger.info("Schema do collector aplicado com sucesso.")
    except Exception as exc:
        logger.warning("apply_schema: %s", exc)
    finally:
        await pool.close()


# ── Scraping ──────────────────────────────────────────────────────────────────

async def _run_scraper(scraper_instance, db_url: str, days: int, label: str) -> dict:
    """
    Helper genérico: instancia pool, executa scrape_by_date e persiste tenders.
    Cada portal recebe seu próprio pool de conexões para isolamento de falhas.
    """
    import asyncpg

    end   = date.today()
    start = end - timedelta(days=max(1, days))

    logger.info("%s: iniciando scraping %s → %s", label, start, end)

    pool = await asyncpg.create_pool(db_url)
    processor = StandaloneTenderProcessor(pool)

    processed = errors = 0
    try:
        await scraper_instance.on_start()
        async for tender in scraper_instance.scrape_by_date(start, end):
            tid = await processor.process(tender)
            if tid:
                processed += 1
                if processed % 50 == 0:
                    logger.info("%s: %d processados...", label, processed)
            else:
                errors += 1
    except Exception as exc:
        logger.error("%s: erro durante scraping: %s", label, exc, exc_info=True)
        errors += 1
    finally:
        await scraper_instance.on_finish()
        await pool.close()

    logger.info("%s: concluído — %d processados, %d erros.", label, processed, errors)
    return {"processed": processed, "errors": errors}


async def run_pncp_scrape(db_url: str, days: int = 1) -> dict:
    """
    Executa scraping PNCP e persiste no banco via StandaloneTenderProcessor.
    Não importa nem usa nenhum broker (RabbitMQ/Redis/Celery).
    """
    from .config import get_settings
    from .scrapers import PNCPScraper

    settings = get_settings()
    scraper  = PNCPScraper(settings)
    return await _run_scraper(scraper, db_url, days, "PNCP")


async def run_comprasnet_scrape(db_url: str, days: int = 1) -> dict:
    """
    Executa scraping ComprasNet via Playwright (headless Chromium).
    Requer que os browsers do Playwright estejam instalados:
        python -m playwright install chromium
    """
    from .config import get_settings
    from .scrapers import ComprasNetScraper

    settings = get_settings()
    scraper  = ComprasNetScraper(settings)
    return await _run_scraper(scraper, db_url, days, "ComprasNet")


async def run_bec_sp_scrape(db_url: str, days: int = 1) -> dict:
    """
    Executa scraping BEC-SP via httpx + BeautifulSoup (sem Playwright).
    """
    from .config import get_settings
    from .scrapers import BECSPScraper

    settings = get_settings()
    scraper  = BECSPScraper(settings)
    return await _run_scraper(scraper, db_url, days, "BEC-SP")


# ── Loop principal ────────────────────────────────────────────────────────────

SKIP_COMPRASNET = os.environ.get("COLLECTOR_SKIP_COMPRASNET", "0") == "1"
SKIP_BEC_SP     = os.environ.get("COLLECTOR_SKIP_BEC_SP", "0") == "1"


async def main_loop() -> None:
    """
    Loop principal do collector standalone:
      1. Aguarda 5 s para o banco ficar pronto
      2. Aplica schema (CREATE TABLE IF NOT EXISTS)
      3. Executa scraping PNCP + ComprasNet + BEC-SP em sequência
      4. Repete a cada INTERVAL_HOURS horas

    Portais podem ser desabilitados individualmente via env vars:
        COLLECTOR_SKIP_COMPRASNET=1  — pula ComprasNet
        COLLECTOR_SKIP_BEC_SP=1      — pula BEC-SP
    """
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        logger.error("DATABASE_URL não configurada — encerrando.")
        sys.exit(1)

    logger.info(
        "Collector standalone iniciado (interval=%dh, days=%d, "
        "skip_comprasnet=%s, skip_bec_sp=%s).",
        INTERVAL_HOURS, SCRAPE_DAYS, SKIP_COMPRASNET, SKIP_BEC_SP,
    )

    # Aguarda o banco estar disponível (útil quando iniciado junto com outros serviços)
    await asyncio.sleep(5)

    await apply_schema(db_url)

    while True:
        cycle_totals = {"processed": 0, "errors": 0}

        # ── PNCP ──────────────────────────────────────────────────────────────
        try:
            result = await run_pncp_scrape(db_url, days=SCRAPE_DAYS)
            cycle_totals["processed"] += result["processed"]
            cycle_totals["errors"]    += result["errors"]
        except Exception as exc:
            logger.error("Erro inesperado no scraping PNCP: %s", exc, exc_info=True)
            cycle_totals["errors"] += 1

        # ── ComprasNet ────────────────────────────────────────────────────────
        if SKIP_COMPRASNET:
            logger.info("ComprasNet: scraping desabilitado (COLLECTOR_SKIP_COMPRASNET=1).")
        else:
            try:
                result = await run_comprasnet_scrape(db_url, days=SCRAPE_DAYS)
                cycle_totals["processed"] += result["processed"]
                cycle_totals["errors"]    += result["errors"]
            except Exception as exc:
                logger.error("Erro inesperado no scraping ComprasNet: %s", exc, exc_info=True)
                cycle_totals["errors"] += 1

        # ── BEC-SP ────────────────────────────────────────────────────────────
        if SKIP_BEC_SP:
            logger.info("BEC-SP: scraping desabilitado (COLLECTOR_SKIP_BEC_SP=1).")
        else:
            try:
                result = await run_bec_sp_scrape(db_url, days=SCRAPE_DAYS)
                cycle_totals["processed"] += result["processed"]
                cycle_totals["errors"]    += result["errors"]
            except Exception as exc:
                logger.error("Erro inesperado no scraping BEC-SP: %s", exc, exc_info=True)
                cycle_totals["errors"] += 1

        logger.info(
            "Ciclo completo — total: %d processados, %d erros.",
            cycle_totals["processed"], cycle_totals["errors"],
        )
        logger.info("Próximo ciclo em %d hora(s).", INTERVAL_HOURS)
        await asyncio.sleep(INTERVAL_HOURS * 3600)


def main() -> None:
    asyncio.run(main_loop())


if __name__ == "__main__":
    main()
