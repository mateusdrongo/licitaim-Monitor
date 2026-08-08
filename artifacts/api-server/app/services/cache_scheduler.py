"""
cache_scheduler.py — Scheduler que atualiza o cache de licitações 4× ao dia.

Usa APScheduler (AsyncIOScheduler) dentro do event loop do FastAPI.
O job varre MODALIDADES_PADRAO × janela de 45 dias e faz upsert no banco.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..api.licitacoes import (
    _fetch_pncp_all_pages_with_cap,
    _fetch_dados_all_pages_with_cap,
    _enrich_licitacoes,
    _fmt_pncp_date,
    MODALIDADES_PADRAO,
    MODALIDADES_DADOSABERTOS,
)
from ..db.session import get_pool
from ..db.licitacoes_repo import upsert_licitacoes, record_global_coverage, CANONICAL_WINDOW_DAYS

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None

# ── Guarda global de sincronização ────────────────────────────────────────────
# Shared por TODOS os callers de sync_licitacoes_job:
#   • APScheduler (crons 4×/dia)
#   • warm-up no startup do FastAPI
#   • endpoint manual POST /admin/sync
# Seguro em asyncio single-thread: nenhum await entre check e set dentro de
# cada invocador.
_sync_in_progress: bool = False


def is_sync_in_progress() -> bool:
    """Retorna True se algum sync estiver em execução (qualquer chamador)."""
    return _sync_in_progress


MAX_PAGES = 50  # cap máximo de páginas por modalidade


async def sync_licitacoes_job() -> dict:
    """
    Varre as modalidades padrão nos últimos CANONICAL_WINDOW_DAYS dias e faz upsert no banco.
    Registra cobertura global com is_complete=True apenas se nenhuma modalidade atingiu o cap
    de páginas (MAX_PAGES). Tenta PNCP primeiro; usa dadosabertos como fallback.
    Retorna {inserted, updated, total, source, is_complete}.

    Gerencia o flag global _sync_in_progress: retorna imediatamente se já houver um sync
    em curso (qualquer chamador — scheduler, warm-up ou manual).
    """
    global _sync_in_progress
    # Verificação + reserva atômica (sem await entre as duas linhas — asyncio não preempta)
    if _sync_in_progress:
        logger.info("cache_scheduler: sync já em andamento, pulando.")
        return {"inserted": 0, "updated": 0, "total": 0, "source": "skip", "is_complete": False}
    _sync_in_progress = True

    try:
        return await _sync_licitacoes_job_impl()
    finally:
        _sync_in_progress = False


async def _sync_licitacoes_job_impl() -> dict:
    """Implementação interna do sync (chamada com _sync_in_progress já reservado)."""
    logger.info("cache_scheduler: iniciando sync...")
    hoje = date.today()
    data_ini_iso = (hoje - timedelta(days=CANONICAL_WINDOW_DAYS)).isoformat()
    data_fim_iso = hoje.isoformat()
    data_ini_pncp = _fmt_pncp_date(data_ini_iso)
    data_fim_pncp = _fmt_pncp_date(data_fim_iso)

    all_results: list[dict] = []
    source = "pncp"
    hit_cap = False  # alguma modalidade atingiu MAX_PAGES sem esgotar os dados?

    # ── 1. Tenta PNCP consulta paginada (todas as páginas até o cap) ─────────
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            for m in MODALIDADES_PADRAO:
                items, capped = await _fetch_pncp_all_pages_with_cap(
                    client, data_ini_pncp, data_fim_pncp, m, max_pages=MAX_PAGES
                )
                all_results.extend(items)
                if capped:
                    hit_cap = True
                logger.info(
                    "cache_scheduler: PNCP modalidade %d → %d itens (capped=%s).",
                    m, len(items), capped,
                )
        logger.info("cache_scheduler: PNCP total=%d itens hit_cap=%s.", len(all_results), hit_cap)
    except Exception as exc:
        logger.warning("cache_scheduler: PNCP falhou (%s), tentando dadosabertos...", exc)

    # ── 2. Fallback dadosabertos paginado ─────────────────────────────────────
    if not all_results:
        hit_cap = False
        source = "dadosabertos"
        base_params: dict = {
            "dataPublicacaoPncpInicial": data_ini_iso,
            "dataPublicacaoPncpFinal":   data_fim_iso,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                for m in MODALIDADES_DADOSABERTOS:
                    items, capped = await _fetch_dados_all_pages_with_cap(
                        client, base_params, m, page_size=100, max_pages=MAX_PAGES
                    )
                    all_results.extend(items)
                    if capped:
                        hit_cap = True
                    logger.info(
                        "cache_scheduler: dadosabertos modalidade %d → %d itens (capped=%s).",
                        m, len(items), capped,
                    )
            logger.info(
                "cache_scheduler: dadosabertos total=%d hit_cap=%s.", len(all_results), hit_cap
            )
        except Exception as exc:
            logger.warning("cache_scheduler: dadosabertos falhou: %s", exc)

    if not all_results:
        logger.warning("cache_scheduler: nenhum resultado — abortando upsert.")
        return {"inserted": 0, "updated": 0, "total": 0, "source": source, "is_complete": False}

    # Dedup por numero antes do enriquecimento
    seen: set[str] = set()
    unique: list[dict] = []
    for item in all_results:
        key = item.get("numero") or item.get("id")
        if key and key not in seen:
            seen.add(key)
            unique.append(item)

    # ── 3. Enriquecimento via API consulta (detalhe individual) ────────────────
    # Busca campos complementares (amparo legal, modo disputa, processo, etc.)
    # com no máximo 5 requisições simultâneas para não sobrecarregar o WAF.
    logger.info("cache_scheduler: enriquecendo %d itens via API consulta...", len(unique))
    try:
        unique = await _enrich_licitacoes(unique, concurrency=5)
        logger.info("cache_scheduler: enriquecimento concluído.")
    except Exception as exc:
        logger.warning("cache_scheduler: enriquecimento falhou, continuando sem ele: %s", exc)

    pool = await get_pool()
    inserted, updated = await upsert_licitacoes(pool, unique, fonte=source)
    total = inserted + updated
    is_complete = not hit_cap

    # Registra cobertura global — is_complete=False se alguma modalidade foi truncada pelo cap.
    await record_global_coverage(pool, total, is_complete=is_complete)

    logger.info(
        "cache_scheduler: sync concluído — %d inseridos, %d atualizados "
        "(fonte: %s, is_complete=%s).",
        inserted, updated, source, is_complete,
    )
    return {
        "inserted": inserted, "updated": updated, "total": total,
        "source": source, "is_complete": is_complete,
    }


def start_scheduler() -> AsyncIOScheduler:
    """Cria e inicia o scheduler. Chame no lifespan do FastAPI."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")

    # Roda 4× ao dia: 00h, 06h, 12h, 18h (horário de Brasília)
    for hour in (0, 6, 12, 18):
        scheduler.add_job(
            sync_licitacoes_job,
            trigger="cron",
            hour=hour,
            minute=0,
            id=f"sync_licitacoes_{hour:02d}h",
            replace_existing=True,
            misfire_grace_time=300,
        )

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
        "(sync 4×/dia | monitores a cada 15min | upcoming 1×/h | "
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
