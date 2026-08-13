"""
cache_scheduler.py — Scheduler de tarefas periódicas (monitores, alertas, saúde do collector).

A sincronização de licitações é responsabilidade exclusiva do collector
(collector/app/standalone.py), que roda a cada ~20 minutos. O endpoint
POST /admin/sync e POST /collector/run delegam a run_one_cycle() do collector
para disparos manuais. Nenhum job de fetch PNCP existe aqui.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _safe_notify_change(tender: dict) -> None:
    """Wrapper fire-and-forget para notify_favorited_tender_changes."""
    try:
        from .tender_change_service import notify_favorited_tender_changes
        result = await notify_favorited_tender_changes(tender)
        logger.debug(
            "_safe_notify_change: numero=%s result=%s", tender.get("numero"), result
        )
    except Exception as exc:
        logger.warning(
            "_safe_notify_change: erro ao notificar numero=%s: %s",
            tender.get("numero"), exc,
        )


def start_scheduler() -> AsyncIOScheduler:
    """Cria e inicia o scheduler. Chame no lifespan do FastAPI."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")

    # Monitor check — a cada 15 minutos
    from ..services.monitor_worker import (
        check_all_monitors,
        check_upcoming_tenders,
        check_document_expirations,
    )

    scheduler.add_job(
        check_all_monitors,
        trigger="interval",
        minutes=15,
        id="check_monitors",
        replace_existing=True,
        misfire_grace_time=60,
    )

    # Tenders abrindo nas próximas 24h — verifica a cada hora
    scheduler.add_job(
        check_upcoming_tenders,
        trigger="interval",
        hours=1,
        id="check_upcoming_tenders",
        replace_existing=True,
        misfire_grace_time=120,
    )

    # Certidões a vencer — verifica 1× ao dia às 07h BRT
    scheduler.add_job(
        check_document_expirations,
        trigger="cron",
        hour=7,
        minute=0,
        id="check_document_expirations",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Tarefas de gerenciamento com prazo vencendo — verifica 1× ao dia às 08h BRT
    from ..services.task_alerts import check_task_deadlines

    scheduler.add_job(
        check_task_deadlines,
        trigger="cron",
        hour=8,
        minute=0,
        id="check_task_deadlines",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Saúde do collector — verifica a cada 30 min e alerta admins se parado
    from ..services.collector_alerts import check_collector_staleness

    scheduler.add_job(
        check_collector_staleness,
        trigger="interval",
        minutes=30,
        id="check_collector_staleness",
        replace_existing=True,
        misfire_grace_time=120,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "cache_scheduler: scheduler iniciado "
        "(monitores a cada 15min | upcoming 1×/h | "
        "certidões 07h BRT | tarefas 08h BRT | collector-health a cada 30min)."
    )
    return scheduler


def stop_scheduler() -> None:
    """Para o scheduler. Chame no shutdown do FastAPI."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("cache_scheduler: scheduler encerrado.")
