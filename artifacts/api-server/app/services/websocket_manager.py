"""
WebSocketManager — gerencia conexões WebSocket por user_id.

Estrutura: {user_id: set[WebSocket]}
Permite entregar notificações em tempo real a clientes conectados.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger("licitaim.websocket")


class WebSocketManager:
    def __init__(self) -> None:
        # user_id (str) → set de conexões ativas
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[user_id].add(websocket)
        logger.info("WS connect: user=%s total=%d", user_id, self._count())

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        self._connections[user_id].discard(websocket)
        if not self._connections[user_id]:
            del self._connections[user_id]
        logger.info("WS disconnect: user=%s total=%d", user_id, self._count())

    # ── Envio ─────────────────────────────────────────────────────────────────

    async def send_personal(self, user_id: str, payload: dict) -> bool:
        """
        Envia payload JSON para todas as conexões do user.
        Retorna True se pelo menos uma entrega foi feita.
        """
        sockets = list(self._connections.get(user_id, set()))
        if not sockets:
            return False

        text = json.dumps(payload, ensure_ascii=False, default=str)
        dead: list[WebSocket] = []
        delivered = 0

        for ws in sockets:
            try:
                await ws.send_text(text)
                delivered += 1
            except Exception:
                dead.append(ws)

        for ws in dead:
            self._connections[user_id].discard(ws)

        return delivered > 0

    async def broadcast(self, payload: dict, exclude_user: Optional[str] = None) -> int:
        """
        Envia para todos os usuários conectados.
        Retorna número de usuários alcançados.
        """
        text = json.dumps(payload, ensure_ascii=False, default=str)
        reached = 0
        for uid, sockets in list(self._connections.items()):
            if uid == exclude_user:
                continue
            for ws in list(sockets):
                try:
                    await ws.send_text(text)
                    reached += 1
                except Exception:
                    sockets.discard(ws)
        return reached

    async def send_ping(self) -> None:
        """Envia ping para manter conexões vivas (chame periodicamente)."""
        for uid, sockets in list(self._connections.items()):
            dead = []
            for ws in list(sockets):
                try:
                    await ws.send_text('{"type":"ping"}')
                except Exception:
                    dead.append(ws)
            for ws in dead:
                sockets.discard(ws)
            if not sockets:
                self._connections.pop(uid, None)

    # ── Info ─────────────────────────────────────────────────────────────────

    def is_connected(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))

    def connected_users(self) -> list[str]:
        return list(self._connections.keys())

    def _count(self) -> int:
        return sum(len(v) for v in self._connections.values())


# ── Singleton ─────────────────────────────────────────────────────────────────
_ws_manager: Optional[WebSocketManager] = None


def get_ws_manager() -> WebSocketManager:
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager
