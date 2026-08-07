"""
PushSender — persiste notificações no banco e entrega via WebSocket (se conectado).
"""
from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger("licitaim.sender.push")


async def send_push(
    user_id: str,
    title: str,
    body: str,
    tipo: str = "info",
    metadata: Optional[dict] = None,
) -> bool:
    """
    1. Salva na tabela `notifications` (entrega persistente).
    2. Se o usuário tiver WebSocket ativo, entrega em tempo real.
    Retorna True em caso de sucesso no banco.
    """
    from ...db.session import get_pool
    from ..websocket_manager import get_ws_manager

    pool = await get_pool()
    try:
        row = await pool.fetchrow(
            """INSERT INTO notifications (user_id, title, body, tipo, channel, metadata)
               VALUES ($1,$2,$3,$4,'push',$5::jsonb)
               RETURNING id, criado_em""",
            user_id, title, body, tipo,
            json.dumps(metadata or {}, default=str),
        )
        notif_id = row["id"]

        payload = {
            "type":      "notification",
            "id":        notif_id,
            "title":     title,
            "body":      body,
            "tipo":      tipo,
            "metadata":  metadata or {},
            "criadoEm":  row["criado_em"].isoformat(),
        }
        ws_manager = get_ws_manager()
        delivered = await ws_manager.send_personal(user_id, payload)
        logger.info(
            "PushSender: user=%s ws_delivered=%s notif_id=%s", user_id, delivered, notif_id
        )
        return True

    except Exception as exc:
        logger.warning("PushSender falhou user=%s: %s", user_id, exc)
        return False
