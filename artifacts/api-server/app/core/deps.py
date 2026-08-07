from fastapi import Cookie, HTTPException, status, Depends
from typing import Optional
import asyncpg
from .security import decode_token
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
    user_id = decode_token(licitaim_token)
    if not user_id:
        raise credentials_exception

    pool = await get_pool()
    user = await pool.fetchrow(
        "SELECT id, nome, email, empresa, cnpj, plano, avatar_url, criado_em "
        "FROM users WHERE id = $1",
        user_id,
    )
    if not user:
        raise credentials_exception
    return dict(user)
