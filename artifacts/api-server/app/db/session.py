import asyncio
import asyncpg
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None
_db_available: bool = False


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


async def init_pool(retries: int = 3, delay: float = 2.0) -> bool:
    """
    Try to create the asyncpg connection pool with up to `retries` attempts,
    waiting `delay` seconds between each.

    Sets the module-level `_db_available` flag to True on success.
    Returns True if the pool was created successfully, False otherwise.
    """
    global _pool, _db_available

    database_url = _resolve_db_url()
    if not database_url:
        logger.critical(
            "DATABASE_URL não configurado — servidor iniciando em modo degradado"
        )
        return False

    for attempt in range(1, retries + 1):
        try:
            _pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
            _db_available = True
            logger.info("DB pool criado com sucesso (tentativa %d/%d)", attempt, retries)
            return True
        except Exception as exc:
            logger.warning(
                "DB pool tentativa %d/%d falhou: %s", attempt, retries, exc
            )
            if attempt < retries:
                await asyncio.sleep(delay)

    logger.critical(
        "Não foi possível conectar ao banco após %d tentativas — modo degradado ativo",
        retries,
    )
    return False


async def get_pool() -> asyncpg.Pool:
    global _pool, _db_available
    if not _db_available or _pool is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="Serviço temporariamente indisponível — banco de dados inacessível",
        )
    return _pool


async def close_pool():
    global _pool, _db_available
    if _pool:
        await _pool.close()
        _pool = None
    _db_available = False
