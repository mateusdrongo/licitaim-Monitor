"""
Celery tasks para scraping periódico dos portais de licitação.

Beat schedule (configurado em celery_app.conf.beat_schedule):
  - scrape_pncp_task: diariamente (ontem → hoje)
  - schedule_daily_scrape: agenda scraping de todos os portais

Uso:
  # Worker
  celery -A collector.app.tasks worker --loglevel=info

  # Beat (agendador)
  celery -A collector.app.tasks beat --loglevel=info
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from celery import Celery
from celery.schedules import crontab

from .config import get_settings

logger = logging.getLogger("collector.tasks")
settings = get_settings()

# ── Celery app ────────────────────────────────────────────────────────────────

celery_app = Celery(
    "collector",
    broker=settings.get_broker_url(),
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Beat schedule
    beat_schedule={
        "scrape-pncp-daily": {
            "task": "collector.app.tasks.scrape_pncp_task",
            "schedule": crontab(hour=2, minute=0),   # 02:00 BRT
            "args": [1],                              # days=1 (ontem)
        },
        "scrape-comprasnet-daily": {
            "task": "collector.app.tasks.scrape_source_task",
            "schedule": crontab(hour=2, minute=30),
            "args": ["comprasnet", 1],
        },
        "scrape-bec-sp-daily": {
            "task": "collector.app.tasks.scrape_source_task",
            "schedule": crontab(hour=3, minute=0),
            "args": ["bec_sp", 1],
        },
        "scrape-bbmnet-daily": {
            "task": "collector.app.tasks.scrape_source_task",
            "schedule": crontab(hour=3, minute=30),
            "args": ["bbmnet", 1],
        },
        "schedule-daily-scrape": {
            "task": "collector.app.tasks.schedule_daily_scrape",
            "schedule": crontab(hour=1, minute=0),   # 01:00 BRT (dispara os outros)
        },
    },
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(coro) -> object:
    """Executa coroutine no event loop (compatível com Celery sync tasks)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


async def _get_pool():
    import asyncpg, os
    return await asyncpg.create_pool(os.environ.get("DATABASE_URL", settings.database_url))


# ── Tasks ─────────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="collector.app.tasks.scrape_pncp_task",
    max_retries=3,
    default_retry_delay=300,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def scrape_pncp_task(self, days: int = 1) -> dict:
    """
    Scraping do PNCP para os últimos `days` dias.
    Processa e persiste cada licitação encontrada.
    """
    end = date.today()
    start = end - timedelta(days=days)
    logger.info("scrape_pncp_task: %s → %s", start, end)
    return _run(_scrape_and_process("pncp", start, end))


@celery_app.task(
    bind=True,
    name="collector.app.tasks.scrape_source_task",
    max_retries=3,
    default_retry_delay=300,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def scrape_source_task(self, source: str, days: int = 1) -> dict:
    """Scraping genérico para qualquer portal por `days` dias."""
    end = date.today()
    start = end - timedelta(days=days)
    logger.info("scrape_source_task[%s]: %s → %s", source, start, end)
    return _run(_scrape_and_process(source, start, end))


@celery_app.task(name="collector.app.tasks.schedule_daily_scrape")
def schedule_daily_scrape() -> dict:
    """
    Celery Beat entry point: agenda scraping diário de todos os portais.
    Disparado uma vez por dia; cada portal tem sua própria task.
    """
    days = 1
    results = {}

    for source in ("pncp", "comprasnet", "bec_sp", "bbmnet"):
        try:
            task = scrape_source_task.apply_async(args=[source, days])
            results[source] = {"task_id": task.id, "status": "queued"}
            logger.info("schedule_daily_scrape: '%s' enfileirado (task %s).", source, task.id)
        except Exception as exc:
            logger.error("schedule_daily_scrape[%s]: %s", source, exc)
            results[source] = {"status": "error", "detail": str(exc)}

    return results


# ── Core async scraping ───────────────────────────────────────────────────────

async def _scrape_and_process(source: str, start: date, end: date) -> dict:
    from .scrapers import PNCPScraper, ComprasNetScraper, BECSPScraper, BBMNetScraper
    from .processors.tender_processor import TenderProcessor
    from .queue import get_publisher

    SCRAPER_MAP = {
        "pncp":       PNCPScraper,
        "comprasnet": ComprasNetScraper,
        "bec_sp":     BECSPScraper,
        "bbmnet":     BBMNetScraper,
    }

    scraper_cls = SCRAPER_MAP.get(source)
    if not scraper_cls:
        return {"error": f"source '{source}' desconhecido"}

    pool = await _get_pool()
    publisher = get_publisher()
    await publisher.connect()

    scraper = scraper_cls()
    processor = TenderProcessor(pool)

    processed = 0
    errors = 0

    try:
        await scraper.on_start()
        async for tender in scraper.scrape_by_date(start, end):
            tid = await processor.process(tender)
            if tid:
                processed += 1
            else:
                errors += 1
    except Exception as exc:
        logger.error("_scrape_and_process[%s]: %s", source, exc)
        errors += 1
    finally:
        await scraper.on_finish()
        await pool.close()
        await publisher.close()

    logger.info(
        "_scrape_and_process[%s]: %d processados, %d erros.",
        source, processed, errors,
    )
    return {"source": source, "start": str(start), "end": str(end),
            "processed": processed, "errors": errors}
