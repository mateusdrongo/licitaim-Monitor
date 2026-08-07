"""
SearchService — orquestra busca entre Elasticsearch (textual) e Postgres (enriquecimento).

Estratégia:
  1. Se ES disponível: executa busca no ES, retorna hits já enriquecidos.
  2. Fallback: busca diretamente no PNCP / mock via licitacoes._fetch_pncp.
  3. Enriquecimento Postgres: para cada resultado, verifica se o user favoritou
     ou tem monitoramento associado àquela licitação.
"""
from __future__ import annotations

import logging
from typing import Optional

from .elasticsearch_service import ElasticsearchService, TenderSearchRequest, get_es_service
from ..db.session import get_pool

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self, es: Optional[ElasticsearchService] = None):
        self._es = es or get_es_service()

    async def search(
        self,
        req: TenderSearchRequest,
        user_id: Optional[str] = None,
    ) -> dict:
        """
        Executa busca e enriquece resultados com dados do Postgres.
        Retorna dict compatível com o schema de /api/licitacoes.
        """
        es_available = await self._es.ping()

        if es_available:
            raw = await self._es.search(req)
            hits = raw.get("hits", [])
            total = raw.get("total", len(hits))
        else:
            # Fallback: mocks / PNCP (importado inline para evitar ciclo)
            logger.info("SearchService: ES offline, usando fallback PNCP/mock.")
            hits, total = await self._fallback_search(req)

        if user_id and hits:
            hits = await self._enrich_with_postgres(hits, user_id)

        return {
            "data":   hits,
            "total":  total,
            "pagina": req.pagina,
            "fonte":  "elasticsearch" if es_available else "pncp_fallback",
        }

    # ── Fallback ──────────────────────────────────────────────────────────────

    async def _fallback_search(self, req: TenderSearchRequest) -> tuple[list, int]:
        from ..api.licitacoes import _fetch_pncp, _normalize, MOCK_LICITACOES

        params: dict = {"pagina": req.pagina, "tamanhoPagina": req.tamanho}
        if req.q:
            params["q"] = req.q
        if req.uf:
            params["uf"] = req.uf[0]

        results = await _fetch_pncp(params)
        if not results:
            results = [_normalize(m) for m in MOCK_LICITACOES]
            # Filtros client-side no fallback
            if req.q:
                ql = req.q.lower()
                results = [r for r in results if ql in r["objeto"].lower() or ql in r["orgao"].lower()]
            if req.uf:
                results = [r for r in results if r["uf"].lower() in [u.lower() for u in req.uf]]
            if req.modalidade:
                results = [r for r in results if r["modalidade"] in req.modalidade]
            if req.valor_min is not None:
                results = [r for r in results if r.get("valorEstimado") and r["valorEstimado"] >= req.valor_min]
            if req.valor_max is not None:
                results = [r for r in results if r.get("valorEstimado") and r["valorEstimado"] <= req.valor_max]

        return results, len(results)

    # ── Enriquecimento Postgres ───────────────────────────────────────────────

    async def _enrich_with_postgres(self, hits: list[dict], user_id: str) -> list[dict]:
        """
        Adiciona flags 'isFavorito' e 'hasMonitoramento' em cada resultado.
        """
        if not hits:
            return hits

        licitacao_ids = [
            h.get("id") or h.get("numeroControlePNCP", "")
            for h in hits
        ]
        licitacao_ids = [lid for lid in licitacao_ids if lid]

        if not licitacao_ids:
            return hits

        try:
            pool = await get_pool()

            # Favoritos do user para essas licitações
            favs = await pool.fetch(
                "SELECT licitacao_id FROM favoritos WHERE user_id = $1 AND licitacao_id = ANY($2::text[])",
                user_id, licitacao_ids,
            )
            fav_ids = {r["licitacao_id"] for r in favs}

            # Monitoramentos (verificamos se algum monitoramento do user tem alertas para essas licitações)
            # Simplificado: não há FK direta; indicamos presença de monitoramentos ativos
            monitored = await pool.fetch(
                "SELECT DISTINCT licitacao_id FROM alertas WHERE user_id = $1 AND licitacao_id = ANY($2::text[])",
                user_id, licitacao_ids,
            )
            monitored_ids = {r["licitacao_id"] for r in monitored}

            for hit in hits:
                lid = hit.get("id") or hit.get("numeroControlePNCP", "")
                hit["isFavorito"] = lid in fav_ids
                hit["hasMonitoramento"] = lid in monitored_ids

        except Exception as exc:
            logger.warning("SearchService enrich: %s", exc)

        return hits


# ── Singleton ─────────────────────────────────────────────────────────────────
_search_service: SearchService | None = None


def get_search_service() -> SearchService:
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
