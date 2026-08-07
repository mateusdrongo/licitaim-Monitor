"""
collector.py — Endpoint de status do collector standalone.
GET /api/collector/status  →  { last_run, processed, errors, next_run_in, is_stale, portals }
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from ..db.session import get_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collector", tags=["collector"])

# Intervalo padrão assumido pelo endpoint quando não há linha no banco.
# Mantido em sincronia com COLLECTOR_INTERVAL_HOURS do standalone.
_DEFAULT_INTERVAL_HOURS = 4


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

        entry = {
            "portal": row["portal"],
            "last_run": last_run_ts.isoformat() if last_run_ts else None,
            "processed": row["processed"] or 0,
            "errors": row["errors"] or 0,
            "next_run_in": next_run_in,
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
    }
