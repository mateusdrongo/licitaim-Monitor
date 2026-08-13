"""
SyncService — sincroniza licitações do Postgres/licitacoes_cache para o Elasticsearch.

O collector é a única fonte de ingestão de dados externos.  O SyncService lê
exclusivamente do banco (`licitacoes_cache`) e indexa no ES — sem chamadas HTTP
a PNCP ou qualquer outra API externa.

Uso:
  - sync_tender(tender_id): busca no cache e indexa no ES
  - sync_all(): indexa todos em lote
  - Hook: chamar schedule_sync() em background após create/update de uma licitação
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .elasticsearch_service import get_es_service
from ..db.session import get_pool

logger = logging.getLogger(__name__)


def _row_to_tender(row: dict) -> dict:
    """Converte uma linha do licitacoes_cache para o schema interno."""
    d = dict(row)
    for k in ("data_publicacao", "data_abertura", "data_encerramento", "atualizado_em"):
        if d.get(k) and hasattr(d[k], "isoformat"):
            d[k] = d[k].isoformat()
    d["data_publicacao_pncp"] = d.pop("data_publicacao", None)
    d["criado_em"] = d.pop("atualizado_em", None)
    d.setdefault("is_favoritada", False)
    return d


class SyncService:
    def __init__(self):
        self._es = get_es_service()

    # ── Single tender ─────────────────────────────────────────────────────────

    async def sync_tender(self, tender_id: str) -> bool:
        """
        Busca a licitação pelo ID no cache do banco e a indexa no ES.
        Retorna True se indexou com sucesso.
        """
        tender = await self._fetch_tender(tender_id)
        if not tender:
            logger.warning("SyncService.sync_tender: '%s' não encontrado no cache.", tender_id)
            return False

        ok = await self._es.index_tender(tender)
        if ok:
            logger.info("SyncService.sync_tender: '%s' indexado.", tender_id)
        return ok

    # ── Bulk sync ─────────────────────────────────────────────────────────────

    async def sync_all(self, batch_size: int = 100) -> dict:
        """
        Sincroniza todos os tenders do cache em lotes para o ES.
        Retorna estatísticas: {indexed, errors, total}.
        """
        all_tenders = await self._fetch_all_tenders()
        total = len(all_tenders)
        total_indexed = 0
        total_errors = 0

        for i in range(0, total, batch_size):
            batch = all_tenders[i : i + batch_size]
            ok, err = await self._es.bulk_index(batch)
            total_indexed += ok
            total_errors += err
            logger.info(
                "SyncService.sync_all: lote %d/%d — %d ok, %d erros.",
                i // batch_size + 1,
                (total + batch_size - 1) // batch_size,
                ok,
                err,
            )

        logger.info(
            "SyncService.sync_all concluído: %d/%d indexados, %d erros.",
            total_indexed, total, total_errors,
        )
        return {"total": total, "indexed": total_indexed, "errors": total_errors}

    # ── Background hook ───────────────────────────────────────────────────────

    def schedule_sync(self, tender_id: str) -> None:
        """
        Dispara sync_tender em background (fire-and-forget).
        Chame após create_or_update de uma licitação.
        """
        asyncio.create_task(
            self._sync_safe(tender_id),
            name=f"es-sync-{tender_id}",
        )

    async def _sync_safe(self, tender_id: str) -> None:
        try:
            await self.sync_tender(tender_id)
        except Exception as exc:
            logger.warning("SyncService background sync(%s): %s", tender_id, exc)

    # ── Data fetching helpers (DB-only) ───────────────────────────────────────

    async def _fetch_tender(self, tender_id: str) -> Optional[dict]:
        """Busca uma licitação pelo id ou numero no licitacoes_cache."""
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT numero, id, ano, objeto, orgao_nome, orgao_cnpj, uf, municipio,
                           modalidade, modalidade_codigo, modo_disputa, situacao, valor_estimado,
                           data_publicacao, data_abertura, data_encerramento,
                           esfera, poder, srp, numero_processo, informacao_complementar,
                           amparo_legal, fonte, atualizado_em
                    FROM licitacoes_cache
                    WHERE id = $1 OR numero = $1
                    LIMIT 1
                    """,
                    tender_id,
                )
            if row:
                return _row_to_tender(row)
        except Exception as exc:
            logger.warning("SyncService._fetch_tender(%s): %s", tender_id, exc)
        return None

    async def _fetch_all_tenders(self) -> list[dict]:
        """
        Retorna todos os tenders do licitacoes_cache.
        Fonte única: banco de dados populado pelo collector.
        """
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT numero, id, ano, objeto, orgao_nome, orgao_cnpj, uf, municipio,
                           modalidade, modalidade_codigo, modo_disputa, situacao, valor_estimado,
                           data_publicacao, data_abertura, data_encerramento,
                           esfera, poder, srp, numero_processo, informacao_complementar,
                           amparo_legal, fonte, atualizado_em
                    FROM licitacoes_cache
                    ORDER BY data_publicacao DESC NULLS LAST, atualizado_em DESC
                    """
                )
            return [_row_to_tender(row) for row in rows]
        except Exception as exc:
            logger.warning("SyncService._fetch_all_tenders: %s", exc)
            return []


# ── Singleton ─────────────────────────────────────────────────────────────────
_sync_service: Optional[SyncService] = None


def get_sync_service() -> SyncService:
    global _sync_service
    if _sync_service is None:
        _sync_service = SyncService()
    return _sync_service
