"""
collector.py — Endpoints do collector standalone.
GET  /api/collector/status  →  { last_run, processed, errors, next_run_in, is_stale, portals, is_running }
POST /api/collector/run     →  inicia ciclo manual (admin only)
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from ..core.admin import get_admin_user
from ..db.session import get_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collector", tags=["collector"])

# Intervalo padrão assumido pelo endpoint quando não há linha no banco.
# Mantido em sincronia com COLLECTOR_INTERVAL_HOURS do standalone.
_DEFAULT_INTERVAL_HOURS = 4

# ── Estado de execução em memória ─────────────────────────────────────────────
# Simples flag para evitar ciclos sobrepostos disparados pelo botão "Executar agora".
_run_lock = asyncio.Lock()
_is_running: bool = False


@router.get("/status")
async def collector_status():
    """
    Retorna o status consolidado do collector standalone.

    Campos:
    - last_run       ISO-8601 da última execução completa (ou null)
    - processed      total de licitações processadas no último ciclo
    - errors         total de erros no último ciclo
    - next_run_in    segundos estimados até o próximo ciclo (ou null)
    - portals        detalhes por portal (pncp, comprasnet, bec_sp)
    """
    pool = await get_pool()

    try:
        rows = await pool.fetch(
            """
            SELECT portal, last_run, processed, errors, interval_hours, atualizado_em
            FROM collector_status
            ORDER BY portal
            """
        )
    except Exception as exc:
        logger.warning("collector_status: falha ao ler tabela: %s", exc)
        return {
            "last_run": None,
            "processed": 0,
            "errors": 0,
            "next_run_in": None,
            "is_stale": True,
            "portals": [],
        }

    if not rows:
        return {
            "last_run": None,
            "processed": 0,
            "errors": 0,
            "next_run_in": None,
            "is_stale": True,
            "portals": [],
        }

    now = datetime.now(timezone.utc)

    portals = []
    global_row = None
    for row in rows:
        last_run_ts = row["last_run"]
        if last_run_ts and last_run_ts.tzinfo is None:
            last_run_ts = last_run_ts.replace(tzinfo=timezone.utc)

        interval_h = row["interval_hours"] or _DEFAULT_INTERVAL_HOURS
        next_run_in: int | None = None
        if last_run_ts:
            elapsed = (now - last_run_ts).total_seconds()
            remaining = interval_h * 3600 - elapsed
            next_run_in = max(0, int(remaining))

        _STALE_THRESHOLD_HOURS = 8
        portal_is_stale: bool
        if last_run_ts is None:
            portal_is_stale = True
            hours_ago = None
        else:
            _elapsed_h = (now - last_run_ts).total_seconds() / 3600
            hours_ago = round(_elapsed_h, 1)
            portal_is_stale = _elapsed_h > _STALE_THRESHOLD_HOURS

        entry = {
            "portal": row["portal"],
            "last_run": last_run_ts.isoformat() if last_run_ts else None,
            "processed": row["processed"] or 0,
            "errors": row["errors"] or 0,
            "next_run_in": next_run_in,
            "is_stale": portal_is_stale,
            "hours_ago": hours_ago,
        }

        if row["portal"] == "global":
            global_row = entry
        else:
            portals.append(entry)

    # Se não existe linha global, agrega os portais individuais
    if global_row is None:
        if portals:
            latest_ts = max(
                (p["last_run"] for p in portals if p["last_run"]),
                default=None,
            )
            total_processed = sum(p["processed"] for p in portals)
            total_errors    = sum(p["errors"]    for p in portals)
            first_next      = next(
                (p["next_run_in"] for p in portals if p["next_run_in"] is not None),
                None,
            )
            global_row = {
                "portal": "global",
                "last_run": latest_ts,
                "processed": total_processed,
                "errors": total_errors,
                "next_run_in": first_next,
            }
        else:
            global_row = {
                "portal": "global",
                "last_run": None,
                "processed": 0,
                "errors": 0,
                "next_run_in": None,
            }

    # Consider stale when last_run is missing or older than 8 h (2× default interval)
    _STALE_THRESHOLD_HOURS = 8
    last_run_iso = global_row["last_run"]
    if last_run_iso is None:
        is_stale = True
    else:
        try:
            last_run_dt = datetime.fromisoformat(last_run_iso)
            if last_run_dt.tzinfo is None:
                last_run_dt = last_run_dt.replace(tzinfo=timezone.utc)
            hours_ago = (now - last_run_dt).total_seconds() / 3600
            is_stale = hours_ago > _STALE_THRESHOLD_HOURS
        except Exception:
            is_stale = True

    return {
        "last_run":    global_row["last_run"],
        "processed":   global_row["processed"],
        "errors":      global_row["errors"],
        "next_run_in": global_row["next_run_in"],
        "is_stale":    is_stale,
        "portals":     portals,
        "is_running":  _is_running,
    }


# ── Collector package path ────────────────────────────────────────────────────
# The API server runs from artifacts/api-server/; the collector package lives
# four directories up at the workspace root. We resolve this once at module
# load time so the import works regardless of CWD.
_WORKSPACE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
)


def _ensure_collector_on_path() -> None:
    """Insert the workspace root into sys.path if it is not already present."""
    import sys
    if _WORKSPACE_ROOT not in sys.path:
        sys.path.insert(0, _WORKSPACE_ROOT)


# Validate that the collector package is reachable at startup (warn, don't crash).
try:
    _ensure_collector_on_path()
    import importlib
    importlib.util.find_spec("collector.app.standalone")  # type: ignore[attr-defined]
    logger.info("collector package found at %s", _WORKSPACE_ROOT)
except Exception as _exc:
    logger.warning("collector package not importable: %s", _exc)


# ── Trigger manual run ────────────────────────────────────────────────────────

async def _run_collection_cycle() -> None:
    """
    Executa um ciclo completo de coleta (PNCP + ComprasNet + BEC-SP) de forma
    assíncrona. Chamado como BackgroundTask pelo endpoint /run.

    O flag _is_running já está definido como True pelo endpoint antes de
    esta função ser enfileirada, garantindo que checagens concorrentes retornem
    409 imediatamente. Esta função só é responsável por resetá-lo no finally.
    """
    global _is_running

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        logger.error("collector/run: DATABASE_URL não configurada.")
        _is_running = False
        return

    logger.info("collector/run: ciclo manual iniciado.")
    try:
        _ensure_collector_on_path()

        from collector.app.standalone import (  # type: ignore[import]
            run_pncp_scrape,
            run_comprasnet_scrape,
            run_bec_sp_scrape,
            _write_collector_status,
            SKIP_COMPRASNET,
            SKIP_BEC_SP,
            SCRAPE_DAYS,
        )

        cycle_totals = {"processed": 0, "errors": 0}

        try:
            result = await run_pncp_scrape(db_url, days=SCRAPE_DAYS)
            cycle_totals["processed"] += result["processed"]
            cycle_totals["errors"]    += result["errors"]
            await _write_collector_status(db_url, "pncp", result["processed"], result["errors"])
        except Exception as exc:
            logger.error("collector/run PNCP: %s", exc, exc_info=True)
            cycle_totals["errors"] += 1

        if not SKIP_COMPRASNET:
            try:
                result = await run_comprasnet_scrape(db_url, days=SCRAPE_DAYS)
                cycle_totals["processed"] += result["processed"]
                cycle_totals["errors"]    += result["errors"]
                await _write_collector_status(db_url, "comprasnet", result["processed"], result["errors"])
            except Exception as exc:
                logger.error("collector/run ComprasNet: %s", exc, exc_info=True)
                cycle_totals["errors"] += 1

        if not SKIP_BEC_SP:
            try:
                result = await run_bec_sp_scrape(db_url, days=SCRAPE_DAYS)
                cycle_totals["processed"] += result["processed"]
                cycle_totals["errors"]    += result["errors"]
                await _write_collector_status(db_url, "bec_sp", result["processed"], result["errors"])
            except Exception as exc:
                logger.error("collector/run BEC-SP: %s", exc, exc_info=True)
                cycle_totals["errors"] += 1

        await _write_collector_status(
            db_url, "global",
            cycle_totals["processed"], cycle_totals["errors"],
        )
        logger.info(
            "collector/run: ciclo manual concluído — %d processados, %d erros.",
            cycle_totals["processed"], cycle_totals["errors"],
        )
    except Exception as exc:
        logger.error("collector/run: erro inesperado: %s", exc, exc_info=True)
    finally:
        _is_running = False


@router.post("/run", status_code=202)
async def collector_run(
    background_tasks: BackgroundTasks,
    _admin: dict = Depends(get_admin_user),
):
    """
    Inicia um ciclo de coleta manual em background (admin only).

    Retorna 202 Accepted imediatamente; o ciclo roda de forma assíncrona.
    Retorna 409 Conflict se já houver um ciclo em andamento.

    A reserva de _is_running ocorre atomicamente sob _run_lock antes de
    enfileirar o BackgroundTask, evitando que dois POSTs concorrentes ambos
    retornem 202.
    """
    global _is_running

    # Atomic check-and-reserve under lock to prevent concurrent triggers
    async with _run_lock:
        if _is_running:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe um ciclo de coleta em andamento.",
            )
        _is_running = True  # Reserve before yielding control

    background_tasks.add_task(_run_collection_cycle)
    return {
        "status": "accepted",
        "message": "Ciclo de coleta iniciado. Acompanhe o status pelo card do Collector.",
    }
