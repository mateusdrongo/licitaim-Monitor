"""
ElasticsearchService — cliente async para indexação e busca de licitações.
Compatível com elasticsearch-py 8.x (AsyncElasticsearch).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from elasticsearch import AsyncElasticsearch, NotFoundError
from elasticsearch.helpers import async_bulk

logger = logging.getLogger(__name__)

INDEX_NAME = "tenders"

# ── Mapping ───────────────────────────────────────────────────────────────────
INDEX_SETTINGS: dict = {
    "settings": {
        "analysis": {
            "analyzer": {
                "brazilian": {
                    "type": "brazilian",
                }
            }
        },
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "objeto":           {"type": "text",    "analyzer": "brazilian"},
            "items_descricao":  {"type": "text",    "analyzer": "brazilian"},
            "orgao":            {"type": "text",    "analyzer": "brazilian",
                                 "fields": {"keyword": {"type": "keyword"}}},
            "uf":               {"type": "keyword"},
            "municipio":        {"type": "keyword"},
            "modalidade":       {"type": "keyword"},
            "situacao":         {"type": "keyword"},
            "numero_controle":  {"type": "keyword"},
            "cnpj_orgao":       {"type": "keyword"},
            "valor_estimado":   {"type": "float"},
            "data_publicacao":  {"type": "date"},
            "data_abertura":    {"type": "date"},
            "srp":              {"type": "boolean"},
        }
    },
}


class TenderSearchRequest:
    """Parâmetros de busca construídos pela camada de rota."""
    def __init__(
        self,
        q: Optional[str] = None,
        modalidade: Optional[list[str]] = None,
        situacao: Optional[list[str]] = None,
        uf: Optional[list[str]] = None,
        valor_min: Optional[float] = None,
        valor_max: Optional[float] = None,
        data_inicio: Optional[str] = None,
        data_fim: Optional[str] = None,
        keywords_excluded: Optional[list[str]] = None,
        pagina: int = 1,
        tamanho: int = 20,
    ):
        self.q = q
        self.modalidade = modalidade or []
        self.situacao = situacao or []
        self.uf = uf or []
        self.valor_min = valor_min
        self.valor_max = valor_max
        self.data_inicio = data_inicio
        self.data_fim = data_fim
        self.keywords_excluded = keywords_excluded or []
        self.pagina = pagina
        self.tamanho = tamanho


class ElasticsearchService:
    def __init__(self, url: str = "http://localhost:9200"):
        self._url = url
        self._client: Optional[AsyncElasticsearch] = None

    def _get_client(self) -> AsyncElasticsearch:
        if self._client is None:
            self._client = AsyncElasticsearch(
                self._url,
                request_timeout=10,
                retry_on_timeout=True,
                max_retries=2,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    # ── Index lifecycle ───────────────────────────────────────────────────────

    async def ensure_index(self) -> bool:
        """Cria o índice 'tenders' se não existir. Retorna True se criou."""
        client = self._get_client()
        try:
            exists = await client.indices.exists(index=INDEX_NAME)
            if exists:
                logger.info("ES: índice '%s' já existe.", INDEX_NAME)
                return False
            await client.indices.create(index=INDEX_NAME, body=INDEX_SETTINGS)
            logger.info("ES: índice '%s' criado com sucesso.", INDEX_NAME)
            return True
        except Exception as exc:
            logger.warning("ES: não foi possível criar o índice: %s", exc)
            return False

    # ── Single document ───────────────────────────────────────────────────────

    async def index_tender(self, tender: dict) -> bool:
        """Indexa/atualiza um tender no ES."""
        client = self._get_client()
        doc_id = tender.get("id") or tender.get("numeroControlePNCP", "")
        body = _to_es_doc(tender)
        try:
            await client.index(index=INDEX_NAME, id=doc_id, document=body)
            return True
        except Exception as exc:
            logger.warning("ES index_tender(%s): %s", doc_id, exc)
            return False

    # ── Bulk ─────────────────────────────────────────────────────────────────

    async def bulk_index(self, tenders: list[dict]) -> tuple[int, int]:
        """
        Bulk indexa uma lista de tenders.
        Retorna (success_count, error_count).
        """
        client = self._get_client()

        def _actions():
            for t in tenders:
                yield {
                    "_index": INDEX_NAME,
                    "_id": t.get("id") or t.get("numeroControlePNCP", ""),
                    "_source": _to_es_doc(t),
                }

        try:
            success, errors = await async_bulk(
                client,
                _actions(),
                raise_on_error=False,
                chunk_size=100,
            )
            if errors:
                logger.warning("ES bulk_index: %d erros.", len(errors))
            return success, len(errors) if isinstance(errors, list) else 0
        except Exception as exc:
            logger.warning("ES bulk_index falhou: %s", exc)
            return 0, len(tenders)

    # ── Search ────────────────────────────────────────────────────────────────

    async def search(self, req: TenderSearchRequest) -> dict:
        """
        Constrói e executa query bool dinamicamente.
        Retorna dict com 'hits', 'total' e 'highlights'.
        """
        client = self._get_client()
        must: list[dict] = []
        filter_: list[dict] = []
        must_not: list[dict] = []

        # Full-text em objeto e numero_controle
        if req.q:
            must.append({
                "multi_match": {
                    "query": req.q,
                    "fields": ["objeto^3", "orgao^2", "items_descricao", "numero_controle"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            })

        # Filtros exatos (terms)
        if req.modalidade:
            filter_.append({"terms": {"modalidade": req.modalidade}})
        if req.situacao:
            filter_.append({"terms": {"situacao": req.situacao}})
        if req.uf:
            filter_.append({"terms": {"uf": req.uf}})

        # Range de valor
        valor_range: dict = {}
        if req.valor_min is not None:
            valor_range["gte"] = req.valor_min
        if req.valor_max is not None:
            valor_range["lte"] = req.valor_max
        if valor_range:
            filter_.append({"range": {"valor_estimado": valor_range}})

        # Range de datas
        data_range: dict = {}
        if req.data_inicio:
            data_range["gte"] = req.data_inicio
        if req.data_fim:
            data_range["lte"] = req.data_fim
        if data_range:
            filter_.append({"range": {"data_publicacao": data_range}})

        # Exclusões
        for kw in req.keywords_excluded:
            must_not.append({"match": {"objeto": kw}})

        bool_query: dict = {}
        if must:
            bool_query["must"] = must
        if filter_:
            bool_query["filter"] = filter_
        if must_not:
            bool_query["must_not"] = must_not
        if not bool_query:
            bool_query["must"] = [{"match_all": {}}]

        from_ = (req.pagina - 1) * req.tamanho

        body: dict[str, Any] = {
            "query": {"bool": bool_query},
            "from": from_,
            "size": req.tamanho,
            "highlight": {
                "fields": {
                    "objeto": {"pre_tags": ["<mark>"], "post_tags": ["</mark>"]},
                    "orgao":  {"pre_tags": ["<mark>"], "post_tags": ["</mark>"]},
                }
            },
            "sort": [
                {"_score": {"order": "desc"}},
                {"data_publicacao": {"order": "desc", "missing": "_last"}},
            ],
        }

        try:
            resp = await client.search(index=INDEX_NAME, body=body)
            hits = resp["hits"]["hits"]
            total = resp["hits"]["total"]["value"]
            results = []
            for h in hits:
                doc = h["_source"]
                doc["_score"] = h["_score"]
                doc["_highlight"] = h.get("highlight", {})
                results.append(doc)
            return {"hits": results, "total": total, "pagina": req.pagina}
        except NotFoundError:
            logger.warning("ES search: índice '%s' não existe.", INDEX_NAME)
            return {"hits": [], "total": 0, "pagina": req.pagina}
        except Exception as exc:
            logger.warning("ES search falhou: %s", exc)
            return {"hits": [], "total": 0, "pagina": req.pagina}

    # ── Ping ─────────────────────────────────────────────────────────────────

    async def ping(self) -> bool:
        try:
            return await self._get_client().ping()
        except Exception:
            return False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_es_doc(tender: dict) -> dict:
    """Converte um tender normalizado para o documento ES (snake_case)."""
    items_desc = tender.get("itemsDescricao") or tender.get("items_descricao") or ""
    if isinstance(items_desc, list):
        items_desc = " ".join(items_desc)
    return {
        "objeto":          tender.get("objeto") or tender.get("objetoCompra", ""),
        "orgao":           tender.get("orgao", ""),
        "cnpj_orgao":     tender.get("cnpjOrgao") or tender.get("cnpj_orgao", ""),
        "unidade":         tender.get("unidade", ""),
        "uf":              tender.get("uf", ""),
        "municipio":       tender.get("municipio", ""),
        "modalidade":      tender.get("modalidade", ""),
        "situacao":        tender.get("situacao", ""),
        "numero_controle": tender.get("numeroControlePNCP") or tender.get("numero_controle", ""),
        "valor_estimado":  tender.get("valorEstimado") or tender.get("valor_estimado"),
        "data_publicacao": _clean_date(tender.get("dataPublicacao") or tender.get("data_publicacao")),
        "data_abertura":   _clean_date(tender.get("dataAbertura") or tender.get("data_abertura")),
        "srp":             tender.get("srp", False),
        "items_descricao": items_desc,
    }


def _clean_date(val: Any) -> Optional[str]:
    if not val:
        return None
    s = str(val)
    # ES aceita yyyy-MM-dd ou ISO-8601; remove hora se presente
    return s[:10] if len(s) >= 10 else None


# ── Singleton ─────────────────────────────────────────────────────────────────
_es_service: Optional[ElasticsearchService] = None


def get_es_service() -> ElasticsearchService:
    global _es_service
    if _es_service is None:
        import os
        url = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
        _es_service = ElasticsearchService(url)
    return _es_service
