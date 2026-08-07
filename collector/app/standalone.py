#!/usr/bin/env python3
"""
standalone.py — Collector standalone sem Redis/Celery/RabbitMQ.

Executa scraping periódico do PNCP usando asyncio puro.
Pode ser iniciado como workflow independente:
    python -m collector.app.standalone

Variáveis de ambiente:
    DATABASE_URL                 — PostgreSQL connection string (obrigatória)
    COLLECTOR_INTERVAL_HOURS     — Intervalo entre ciclos (padrão: 4)
    COLLECTOR_DAYS               — Janela de dias para trás (padrão: 1)
    LOG_LEVEL                    — Nível de log (padrão: INFO)
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

async def run_pncp_scrape(db_url: str, days: int = 1) -> dict:
    """
    Executa scraping PNCP e persiste no banco via StandaloneTenderProcessor.
    Não importa nem usa nenhum broker (RabbitMQ/Redis/Celery).
    """
    import asyncpg
    from .config import get_settings
    from .scrapers import PNCPScraper

    settings = get_settings()
    end   = date.today()
    start = end - timedelta(days=max(1, days))

    logger.info("Iniciando scraping PNCP: %s → %s", start, end)

    pool = await asyncpg.create_pool(db_url)
    scraper   = PNCPScraper(settings)
    processor = StandaloneTenderProcessor(pool)

    processed = errors = 0
    try:
        await scraper.on_start()
        async for tender in scraper.scrape_by_date(start, end):
            tid = await processor.process(tender)
            if tid:
                processed += 1
                if processed % 50 == 0:
                    logger.info("Progresso: %d processados...", processed)
            else:
                errors += 1
    except Exception as exc:
        logger.error("Erro durante scraping: %s", exc, exc_info=True)
        errors += 1
    finally:
        await scraper.on_finish()
        await pool.close()

    logger.info("Scraping concluído: %d processados, %d erros.", processed, errors)
    return {"processed": processed, "errors": errors}


# ── Loop principal ────────────────────────────────────────────────────────────

async def main_loop() -> None:
    """
    Loop principal do collector standalone:
      1. Aguarda 5 s para o banco ficar pronto
      2. Aplica schema (CREATE TABLE IF NOT EXISTS)
      3. Executa scraping PNCP imediatamente
      4. Repete a cada INTERVAL_HOURS horas
    """
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        logger.error("DATABASE_URL não configurada — encerrando.")
        sys.exit(1)

    logger.info(
        "Collector standalone iniciado (interval=%dh, days=%d).",
        INTERVAL_HOURS, SCRAPE_DAYS,
    )

    # Aguarda o banco estar disponível (útil quando iniciado junto com outros serviços)
    await asyncio.sleep(5)

    await apply_schema(db_url)

    while True:
        try:
            result = await run_pncp_scrape(db_url, days=SCRAPE_DAYS)
            logger.info("Ciclo concluído: %s", result)
        except Exception as exc:
            logger.error("Erro inesperado no ciclo: %s", exc, exc_info=True)

        logger.info("Próximo ciclo em %d hora(s).", INTERVAL_HOURS)
        await asyncio.sleep(INTERVAL_HOURS * 3600)


def main() -> None:
    asyncio.run(main_loop())


if __name__ == "__main__":
    main()
