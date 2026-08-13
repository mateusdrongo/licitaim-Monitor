from fastapi import Cookie, HTTPException, status, Depends
from typing import Optional
from datetime import datetime, timezone
import asyncpg
from .security import decode_token, decode_token_full
from ..db.session import get_pool


async def get_current_user(
    licitaim_token: Optional[str] = Cookie(default=None),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autenticado",
    )
    if not licitaim_token:
        raise credentials_exception

    payload = decode_token_full(licitaim_token)
    if not payload:
        raise credentials_exception

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception

    pool = await get_pool()
    user = await pool.fetchrow(
        "SELECT id, nome, email, empresa, cnpj, plano, avatar_url, criado_em, "
        "notif_email, notif_telegram, telegram_chat_id, session_version "
        "FROM users WHERE id = $1",
        user_id,
    )
    if not user:
        raise credentials_exception

    # Session revocation: compare the session version in the JWT (sv claim) against
    # the current version stored on the user row. When a password is reset, session_version
    # is incremented; any token carrying an older version is rejected.
    # Legacy tokens with no sv claim are treated as sv=0.  Users who have never reset
    # their password keep session_version=0, so legacy tokens remain valid for them.
    # Once a reset occurs (session_version > 0), any token without sv=current is rejected.
    token_sv = payload.get("sv", 0)
    if token_sv != user["session_version"]:
        raise credentials_exception

    return dict(user)
