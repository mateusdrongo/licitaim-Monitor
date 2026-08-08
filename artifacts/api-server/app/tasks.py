"""
Celery tasks para LicitAIM API.

Worker:   celery -A app.tasks worker --loglevel=info
Beat:     celery -A app.tasks beat   --loglevel=info
"""
from __future__ import annotations

import asyncio
import logging

from celery import Celery
from celery.schedules import crontab

from .core.config import get_settings

logger = logging.getLogger("licitaim.tasks")
settings = get_settings()

# ── Celery app ────────────────────────────────────────────────────────────────

celery_app = Celery(
    "licitaim",
    broker=settings.get_celery_broker(),
    backend=settings.get_celery_backend(),
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
    beat_schedule={
        # A cada 15 min: verifica monitores
        "check-monitors-15min": {
            "task":     "app.tasks.check_monitors",
            "schedule": crontab(minute="*/15"),
        },
        # A cada 15 min: notifica favoritos com mudanças detectadas pelo collector
        "check-favorited-changes-15min": {
            "task":     "app.tasks.check_favorited_tender_changes",
            "schedule": crontab(minute="*/15"),
        },
        # A cada 1h: alerta licitações que abrem em 24h
        "check-upcoming-1h": {
            "task":     "app.tasks.check_upcoming",
            "schedule": crontab(minute=0),   # no início de cada hora
        },
        # Diário 08:00 BRT: verifica vencimento de certidões
        "check-documents-daily": {
            "task":     "app.tasks.check_documents",
            "schedule": crontab(hour=8, minute=0),
        },
    },
)


# ── Helper: executa coroutine em tasks síncronas ──────────────────────────────

def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ── Tasks ─────────────────────────────────────────────────────────────────────

@celery_app.task(
    name="app.tasks.check_monitors",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def check_monitors(self) -> dict:
    """
    Verifica todos os monitores ativos, busca novos tenders no ES
    desde last_checked_at e notifica usuários.
    Roda a cada 15 minutos.
    """
    logger.info("Task check_monitors iniciando.")
    from .services.monitor_worker import check_all_monitors
    result = _run(check_all_monitors())
    logger.info("Task check_monitors concluído: %s", result)
    return result


@celery_app.task(
    name="app.tasks.check_upcoming",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def check_upcoming(self) -> dict:
    """
    Alerta usuários sobre licitações favoritas que abrem nas próximas 24h.
    Roda a cada 1 hora.
    """
    logger.info("Task check_upcoming iniciando.")
    from .services.monitor_worker import check_upcoming_tenders
    result = _run(check_upcoming_tenders())
    logger.info("Task check_upcoming concluído: %s", result)
    return result


@celery_app.task(
    name="app.tasks.check_documents",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
    autoretry_for=(Exception,),
)
def check_documents(self) -> dict:
    """
    Verifica vencimento de certidões e envia alertas.
    Roda diariamente às 08:00 BRT.
    """
    logger.info("Task check_documents iniciando.")
    from .services.monitor_worker import check_document_expirations
    result = _run(check_document_expirations())
    logger.info("Task check_documents concluído: %s", result)
    return result


@celery_app.task(
    name="app.tasks.check_favorited_tender_changes",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def check_favorited_tender_changes(self) -> dict:
    """
    Varre tender_history para mudanças em licitações favoritadas e notifica
    os usuários afetados via e-mail e Telegram.
    Roda a cada 15 minutos, alinhado com check_monitors.
    """
    logger.info("Task check_favorited_tender_changes iniciando.")
    from .services.monitor_worker import check_favorited_tender_changes as _check
    result = _run(_check())
    logger.info("Task check_favorited_tender_changes concluído: %s", result)
    return result
