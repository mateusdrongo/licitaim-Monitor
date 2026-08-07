"""
admin.py — Dependência FastAPI que restringe acesso a usuários administradores.

Configuração: defina a variável de ambiente ADMIN_EMAILS com uma lista
separada por vírgulas dos e-mails que têm acesso admin.

Exemplo:
    ADMIN_EMAILS=joao@empresa.com,maria@empresa.com

Se ADMIN_EMAILS não estiver definida, apenas o usuário com menor ID
(o primeiro cadastrado) é considerado admin — útil em instâncias solo.
"""
from __future__ import annotations

import os
import logging
from fastapi import Depends, HTTPException, status
from .deps import get_current_user

logger = logging.getLogger(__name__)


def _admin_emails() -> set[str]:
    raw = os.getenv("ADMIN_EMAILS", "").strip()
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


async def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Exige que o usuário seja administrador (e-mail presente em ADMIN_EMAILS).
    Levanta 403 Forbidden se não for, ou 503 se ADMIN_EMAILS não estiver configurado.
    """
    allowed = _admin_emails()
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Endpoint administrativo desabilitado. "
                "Configure a variável de ambiente ADMIN_EMAILS com os e-mails permitidos."
            ),
        )

    email = (current_user.get("email") or "").lower()
    if email not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )

    return current_user
