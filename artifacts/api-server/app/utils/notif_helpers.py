"""
Utilitários compartilhados de notificação para jobs em background.

Este módulo centraliza o helper _fetch_with_notif_fallback e os valores
padrão de preferências de notificação (_NOTIF_DEFAULTS) para que qualquer
novo worker ou job possa importá-los diretamente, evitando cópias do
padrão try/except espalhadas pela base de código.

Uso típico
----------
    from app.utils.notif_helpers import fetch_with_notif_fallback, NOTIF_DEFAULTS

    rows = await fetch_with_notif_fallback(
        pool,
        full_query=...,
        fallback_query=...,
        args=(...,),
        context="nome_da_funcao_chamadora",
    )
"""
from __future__ import annotations

import logging

logger = logging.getLogger("licitaim.notif_helpers")

# Valores padrão de preferências de notificação usados quando as colunas
# correspondentes na tabela users ainda não existem (schema drift / migration
# pendente).  Qualquer novo worker deve usar este dicionário em vez de
# duplicar os valores.
NOTIF_DEFAULTS: dict = dict(
    notif_email=True, notif_push=True,
    notif_whatsapp=False, notif_telegram=False,
    telegram_chat_id=None, phone=None,
)


async def fetch_with_notif_fallback(
    pool,
    full_query: str,
    fallback_query: str,
    args: tuple,
    context: str,
) -> list:
    """
    Executa full_query (que inclui colunas de notificação no JOIN com users).
    Se falhar (coluna ausente ou outro erro de schema), executa fallback_query
    (sem essas colunas) e mescla NOTIF_DEFAULTS em cada linha.

    Parâmetros
    ----------
    pool           : asyncpg pool
    full_query     : SQL completo, com colunas notif_* de users
    fallback_query : SQL sem colunas notif_*, apenas email/nome
    args           : argumentos posicionais para ambas as queries
    context        : nome da função chamadora, usado no log de aviso
    """
    try:
        return list(await pool.fetch(full_query, *args))
    except Exception as exc:
        logger.warning(
            "%s: colunas de notificação indisponíveis, usando preferências padrão: %s",
            context, exc,
        )
        rows = await pool.fetch(fallback_query, *args)
        return [dict(r, **NOTIF_DEFAULTS) for r in rows]
