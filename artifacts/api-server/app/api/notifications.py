"""
Notifications API — gerencia notificações push do usuário (tabela `notifications`).
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional
from ..core.deps import get_current_user
from ..db.session import get_pool

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _fmt(row: dict) -> dict:
    d = dict(row)
    d["criadoEm"] = d.pop("criado_em").isoformat() if d.get("criado_em") else None
    return d


@router.get("")
async def list_notifications(
    lida: Optional[bool] = Query(None),
    limit: int = Query(50, le=100),
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    uid = current_user["id"]

    conditions = ["user_id=$1"]
    values: list = [uid]
    idx = 2

    if lida is not None:
        conditions.append(f"lida=${idx}"); values.append(lida); idx += 1

    where = " AND ".join(conditions)
    rows = await pool.fetch(
        f"SELECT id, title, body, tipo, channel, lida, metadata, criado_em "
        f"FROM notifications WHERE {where} ORDER BY criado_em DESC LIMIT {limit}",
        *values,
    )
    total_nao_lidas = await pool.fetchval(
        "SELECT COUNT(*) FROM notifications WHERE user_id=$1 AND lida=false", uid
    )
    return {
        "data": [_fmt(dict(r)) for r in rows],
        "total": len(rows),
        "totalNaoLidas": int(total_nao_lidas or 0),
    }


@router.post("/{notif_id}/ler")
async def marcar_lida(notif_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    await pool.execute(
        "UPDATE notifications SET lida=true WHERE id=$1 AND user_id=$2",
        notif_id, current_user["id"],
    )
    return {"ok": True}


@router.post("/ler-todas")
async def marcar_todas_lidas(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    await pool.execute(
        "UPDATE notifications SET lida=true WHERE user_id=$1 AND lida=false",
        current_user["id"],
    )
    return {"ok": True}


@router.delete("/{notif_id}", status_code=204)
async def delete_notification(notif_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    await pool.execute(
        "DELETE FROM notifications WHERE id=$1 AND user_id=$2",
        notif_id, current_user["id"],
    )
