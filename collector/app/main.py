#!/usr/bin/env python3
"""
collector CLI — entry point para execução manual do scraping.

Exemplos:
  python -m collector.app.main scrape --source pncp --days 1
  python -m collector.app.main scrape --source comprasnet --days 7
  python -m collector.app.main scrape --source pncp --date 2025-01-15
  python -m collector.app.main sync-schema
  python -m collector.app.main consume-queue
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import date, timedelta

# Garante que o pacote collector/ está no path ao rodar via python diretamente
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from collector.app.config import get_settings

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("collector.cli")


# ── Comandos ──────────────────────────────────────────────────────────────────

async def cmd_scrape(source: str, days: int, target_date: str | None) -> None:
    import asyncpg
    from collector.app.scrapers import PNCPScraper, ComprasNetScraper, BECSPScraper, BBMNetScraper
    from collector.app.processors.tender_processor import TenderProcessor
    from collector.app.queue import get_publisher

    SCRAPER_MAP = {
        "pncp":       PNCPScraper,
        "comprasnet": ComprasNetScraper,
        "bec_sp":     BECSPScraper,
        "bbmnet":     BBMNetScraper,
    }

    scraper_cls = SCRAPER_MAP.get(source)
    if not scraper_cls:
        logger.error("Source desconhecido: '%s'. Opções: %s", source, list(SCRAPER_MAP))
        sys.exit(1)

    if target_date:
        start = end = date.fromisoformat(target_date)
    else:
        end = date.today()
        start = end - timedelta(days=max(1, days))

    settings = get_settings()
    pool = await asyncpg.create_pool(settings.database_url or os.environ["DATABASE_URL"])
    publisher = get_publisher()
    await publisher.connect()

    scraper = scraper_cls()
    processor = TenderProcessor(pool)

    processed = errors = 0
    logger.info("Iniciando scraping [%s] de %s → %s", source, start, end)

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
    finally:
        await scraper.on_finish()
        await pool.close()
        await publisher.close()

    logger.info("Concluído: %d processados, %d erros.", processed, errors)


async def cmd_sync_schema() -> None:
    """
    Cria/atualiza as tabelas do collector e faz back-fill das colunas normalizadas.
    Delega para standalone.apply_schema, que é a única implementação canônica
    e também é executada na inicialização do collector standalone.
    """
    from .standalone import apply_schema
    settings = get_settings()
    db_url = settings.database_url or os.environ.get("DATABASE_URL", "")
    if not db_url:
        logger.error("DATABASE_URL não configurada.")
        sys.exit(1)
    await apply_schema(db_url)
    logger.info("sync-schema concluído.")


async def cmd_consume_queue() -> None:
    """Inicia consumer RabbitMQ para processar eventos de sync ES."""
    from collector.app.queue import start_es_consumer
    logger.info("Iniciando consumer RabbitMQ (Ctrl+C para parar)...")
    await start_es_consumer()


# ── CLI parser ────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="collector",
        description="LicitAIM Collector — scraping de portais de licitação",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # scrape
    p_scrape = sub.add_parser("scrape", help="Executa scraping de um portal")
    p_scrape.add_argument(
        "--source", "-s",
        required=True,
        choices=["pncp", "comprasnet", "bec_sp", "bbmnet"],
        help="Portal a scraping",
    )
    p_scrape.add_argument(
        "--days", "-d",
        type=int,
        default=1,
        help="Número de dias para trás (padrão: 1)",
    )
    p_scrape.add_argument(
        "--date",
        dest="target_date",
        default=None,
        help="Data específica YYYY-MM-DD (ignora --days)",
    )

    # sync-schema
    sub.add_parser("sync-schema", help="Cria/atualiza tabelas no banco de dados")

    # consume-queue
    sub.add_parser("consume-queue", help="Inicia consumer RabbitMQ para sync ES")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "scrape":
        asyncio.run(cmd_scrape(args.source, args.days, args.target_date))
    elif args.command == "sync-schema":
        asyncio.run(cmd_sync_schema())
    elif args.command == "consume-queue":
        asyncio.run(cmd_consume_queue())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
