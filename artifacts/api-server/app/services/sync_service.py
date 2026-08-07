"""
SyncService — sincroniza licitações do Postgres/PNCP para o Elasticsearch.

Uso:
  - sync_tender(tender_id): busca no PNCP/mock e indexa no ES
  - sync_all(): indexa todos em lote
  - Hook: chamar sync_tender() em background após create/update de uma licitação
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from datetime import date, timedelta
from .elasticsearch_service import get_es_service
from ..api.licitacoes import _normalize, _normalize_pncp_item, _fetch_dadosabertos, MOCK_LICITACOES, MODALIDADES_DADOSABERTOS

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(self):
        self._es = get_es_service()

    # ── Single tender ─────────────────────────────────────────────────────────

    async def sync_tender(self, tender_id: str) -> bool:
        """
        Busca a licitação pelo ID (mock ou PNCP) e a indexa no ES.
        Retorna True se indexou com sucesso.
        """
        tender = await self._fetch_tender(tender_id)
        if not tender:
            logger.warning("SyncService.sync_tender: '%s' não encontrado.", tender_id)
            return False

        ok = await self._es.index_tender(tender)
        if ok:
            logger.info("SyncService.sync_tender: '%s' indexado.", tender_id)
        return ok

    # ── Bulk sync ─────────────────────────────────────────────────────────────

    async def sync_all(self, batch_size: int = 100) -> dict:
        """
        Sincroniza todos os tenders disponíveis em lotes.
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

    # ── Data fetching helpers ─────────────────────────────────────────────────

    async def _fetch_tender(self, tender_id: str) -> Optional[dict]:
        # 1. Tenta nos mocks locais
        mock = next(
            (m for m in MOCK_LICITACOES if m.get("id") == tender_id or m.get("numeroControlePNCP") == tender_id),
            None,
        )
        if mock:
            return _normalize(mock)

        # 2. Tenta no PNCP
        parts = tender_id.split("-")
        if len(parts) >= 3:
            cnpj, ano, seq = parts[0], parts[1], parts[2]
            import httpx
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(
                        f"https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{seq}"
                    )
                    if resp.status_code == 200:
                        return _normalize_pncp_item(resp.json())
            except Exception as exc:
                logger.warning("SyncService PNCP fetch(%s): %s", tender_id, exc)

        return None

    async def _fetch_all_tenders(self) -> list[dict]:
        """
        Retorna todos os tenders disponíveis.
        Prioriza dados do PNCP; usa mocks como fallback/base.
        """
        # Tenta buscar do PNCP (paginado)
        # Busca via dadosabertos.compras.gov.br em paralelo por modalidade
        hoje = date.today()
        params = {
            "pagina": 1, "tamanhoPagina": 500,
            "dataPublicacaoPncpInicial": (hoje - timedelta(days=30)).isoformat(),
            "dataPublicacaoPncpFinal":   hoje.isoformat(),
        }
        import httpx
        all_results: list[dict] = []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                tasks = [_fetch_dadosabertos(client, params, m) for m in MODALIDADES_DADOSABERTOS]
                batches = await asyncio.gather(*tasks, return_exceptions=True)
            for batch in batches:
                if isinstance(batch, list):
                    all_results.extend(batch)
        except Exception as exc:
            logger.warning("SyncService _fetch_all_tenders: %s", exc)

        if all_results:
            return all_results

        # Fallback: mocks
        return [_normalize(m) for m in MOCK_LICITACOES]


# ── Singleton ─────────────────────────────────────────────────────────────────
_sync_service: Optional[SyncService] = None


def get_sync_service() -> SyncService:
    global _sync_service
    if _sync_service is None:
        _sync_service = SyncService()
    return _sync_service
