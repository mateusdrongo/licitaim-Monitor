"""
test_search_after_collector_cycle.py

Testes de integração que verificam a cadeia Collector-First:

  1. Registros inseridos em licitacoes_cache aparecem em GET /licitacoes.
  2. GET /licitacoes/{id} retorna os dados corretos quando o ID existe.
  3. GET /licitacoes/{id} retorna 404 quando o ID não existe — sem tentativa
     de chamar APIs externas.
  4. GET /licitacoes com filtros (uf, q, modalidade) repassa os parâmetros
     corretos para search_licitacoes_cache.
  5. GET /licitacoes responde com source="banco" e queued=False em todos os
     cenários — nunca com source="pncp", "dadosabertos" ou "mock".

Estratégia: FastAPI mini-app com apenas o router de licitacoes, pool e
search_licitacoes_cache substituídos por mocks em memória.  Nenhuma conexão
real com banco é feita.
"""
from __future__ import annotations

import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api.licitacoes import router as licitacoes_router  # noqa: E402
from app.core.deps import get_current_user                  # noqa: E402


# ── App mínimo — sem scheduler/lifespan de produção ──────────────────────────

def _make_app() -> FastAPI:
    mini = FastAPI()
    # O router já carrega prefix="/licitacoes"; incluímos com "/api" para que
    # os endpoints fiquem em /api/licitacoes e /api/licitacoes/{id}.
    mini.include_router(licitacoes_router, prefix="/api")
    return mini


# ── Usuário autenticado padrão para todos os testes ──────────────────────────

def _auth_user() -> dict:
    return {"id": 1, "nome": "Tester", "email": "tester@example.com"}


# ── Linhas de amostra da licitacoes_cache ─────────────────────────────────────

_SAMPLE_ROW_1 = {
    "id": "abc-001",
    "numero": "00100000001202400001",
    "objeto": "Aquisição de equipamentos de TI",
    "situacao": "aberta",
    "modalidade_codigo": 6,
    "uf": "SP",
    "valor_estimado": 150000.00,
    "orgao_nome": "Prefeitura de São Paulo",
    "data_publicacao_pncp": "2024-01-15",
    "fonte": "pncp",
}

_SAMPLE_ROW_2 = {
    "id": "abc-002",
    "numero": "00200000001202400002",
    "objeto": "Contratação de serviços de limpeza",
    "situacao": "encerrada",
    "modalidade_codigo": 4,
    "uf": "RJ",
    "valor_estimado": 80000.00,
    "orgao_nome": "Governo do Estado do RJ",
    "data_publicacao_pncp": "2024-01-10",
    "fonte": "comprasnet",
}


# ── Mock de pool para get_licitacao (usa fetchrow diretamente) ───────────────

class _MockPool:
    """
    Pool falso que simula licitacoes_cache em memória.
    `rows` é uma lista de dicts que representam linhas da tabela.
    """

    def __init__(self, rows: list[dict]):
        # Converte para objetos que permitem acesso por chave e dict()
        self._rows = rows

    async def fetchrow(self, query: str, *args):
        q = query.strip().lower()
        if not args:
            return None

        if "numero = $1" in q and "id = $1 or numero = $2" not in q:
            numero = args[0]
            for row in self._rows:
                if row.get("numero") == numero:
                    return _DictRecord(row)
            return None

        if "id = $1 or numero = $2" in q:
            id_val = args[0]
            for row in self._rows:
                if row.get("id") == id_val or row.get("numero") == id_val:
                    return _DictRecord(row)
            return None

        return None

    async def fetch(self, query: str, *args):
        return []

    async def execute(self, query: str, *args):
        pass


class _DictRecord(dict):
    """Comporta-se como asyncpg.Record: suporta dict() e acesso por chave."""
    pass


# ── Fixture: injeta pool e search_licitacoes_cache mockados ──────────────────

@pytest.fixture
def _fake_pool_two_rows():
    return _MockPool([_SAMPLE_ROW_1, _SAMPLE_ROW_2])


@pytest.fixture
def _fake_pool_empty():
    return _MockPool([])


# ── 1. Registros inseridos aparecem em GET /licitacoes ───────────────────────

class TestSearchReturnsInsertedRows:
    """
    Verifica que registros gravados em licitacoes_cache pelo coletor aparecem
    corretamente na resposta de GET /licitacoes.
    """

    def test_returns_rows_from_cache(self, _fake_pool_two_rows):
        """
        Quando search_licitacoes_cache devolve duas linhas, GET /licitacoes
        deve retornar ambas com total=2.
        """
        app = _make_app()
        app.dependency_overrides[get_current_user] = _auth_user

        with patch(
            "app.api.licitacoes.get_pool",
            new=AsyncMock(return_value=_fake_pool_two_rows),
        ), patch(
            "app.api.licitacoes.search_licitacoes_cache",
            new=AsyncMock(return_value=([_SAMPLE_ROW_1, _SAMPLE_ROW_2], 2)),
        ):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/api/licitacoes")

        assert resp.status_code == 200, f"Esperava 200, recebeu {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["total"] == 2, f"total esperado=2, recebido={body['total']}"
        assert len(body["data"]) == 2, f"data esperado 2 itens, recebido={len(body['data'])}"

    def test_source_is_always_banco(self):
        """
        source deve ser 'banco' e queued deve ser False — nunca 'pncp',
        'dadosabertos' ou 'mock'.
        """
        app = _make_app()
        app.dependency_overrides[get_current_user] = _auth_user

        with patch(
            "app.api.licitacoes.get_pool",
            new=AsyncMock(return_value=_MockPool([])),
        ), patch(
            "app.api.licitacoes.search_licitacoes_cache",
            new=AsyncMock(return_value=([], 0)),
        ):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/api/licitacoes")

        body = resp.json()
        assert body.get("source") == "banco", (
            f"source deveria ser 'banco', recebeu {body.get('source')!r}"
        )
        assert body.get("queued") is False, (
            f"queued deveria ser False, recebeu {body.get('queued')!r}"
        )

    def test_empty_cache_returns_zero_results(self):
        """Banco vazio devolve total=0 e data=[] sem erro."""
        app = _make_app()
        app.dependency_overrides[get_current_user] = _auth_user

        with patch(
            "app.api.licitacoes.get_pool",
            new=AsyncMock(return_value=_MockPool([])),
        ), patch(
            "app.api.licitacoes.search_licitacoes_cache",
            new=AsyncMock(return_value=([], 0)),
        ):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/api/licitacoes")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["data"] == []

    def test_pagination_fields_present(self):
        """Resposta deve sempre incluir page, total_pages, total, data."""
        app = _make_app()
        app.dependency_overrides[get_current_user] = _auth_user

        with patch(
            "app.api.licitacoes.get_pool",
            new=AsyncMock(return_value=_MockPool([])),
        ), patch(
            "app.api.licitacoes.search_licitacoes_cache",
            new=AsyncMock(return_value=([_SAMPLE_ROW_1], 1)),
        ):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/api/licitacoes")

        body = resp.json()
        for field in ("data", "total", "page", "total_pages", "source", "queued"):
            assert field in body, f"Campo '{field}' ausente na resposta: {list(body.keys())}"


# ── 2. Filtros são repassados a search_licitacoes_cache ──────────────────────

class TestSearchFiltersForwarded:
    """
    Verifica que os filtros passados na query string chegam corretamente
    à função search_licitacoes_cache.
    """

    def test_uf_filter_forwarded(self):
        """Parâmetro uf= deve ser repassado a search_licitacoes_cache."""
        app = _make_app()
        app.dependency_overrides[get_current_user] = _auth_user
        mock_search = AsyncMock(return_value=([], 0))

        with patch("app.api.licitacoes.get_pool", new=AsyncMock(return_value=_MockPool([]))), \
             patch("app.api.licitacoes.search_licitacoes_cache", new=mock_search):
            with TestClient(app, raise_server_exceptions=False) as client:
                client.get("/api/licitacoes?uf=SP")

        _, kwargs = mock_search.call_args
        assert kwargs.get("uf") == "SP", (
            f"uf='SP' não chegou a search_licitacoes_cache: kwargs={kwargs}"
        )

    def test_q_filter_forwarded(self):
        """Parâmetro q= deve ser repassado a search_licitacoes_cache."""
        app = _make_app()
        app.dependency_overrides[get_current_user] = _auth_user
        mock_search = AsyncMock(return_value=([], 0))

        with patch("app.api.licitacoes.get_pool", new=AsyncMock(return_value=_MockPool([]))), \
             patch("app.api.licitacoes.search_licitacoes_cache", new=mock_search):
            with TestClient(app, raise_server_exceptions=False) as client:
                client.get("/api/licitacoes?q=equipamentos")

        _, kwargs = mock_search.call_args
        assert kwargs.get("q") == "equipamentos", (
            f"q='equipamentos' não chegou a search_licitacoes_cache: kwargs={kwargs}"
        )

    def test_somente_vigentes_sets_situacao_aberta(self):
        """somenteVigentes=true deve resultar em situacao='aberta' para search_licitacoes_cache."""
        app = _make_app()
        app.dependency_overrides[get_current_user] = _auth_user
        mock_search = AsyncMock(return_value=([], 0))

        with patch("app.api.licitacoes.get_pool", new=AsyncMock(return_value=_MockPool([]))), \
             patch("app.api.licitacoes.search_licitacoes_cache", new=mock_search):
            with TestClient(app, raise_server_exceptions=False) as client:
                client.get("/api/licitacoes?somenteVigentes=true")

        _, kwargs = mock_search.call_args
        assert kwargs.get("situacao") == "aberta", (
            f"somenteVigentes=true deveria resultar em situacao='aberta', "
            f"recebeu situacao={kwargs.get('situacao')!r}"
        )


# ── 3. GET /licitacoes/{id} — registro existente ─────────────────────────────

class TestGetLicitacaoById:
    """
    Verifica que GET /licitacoes/{id} serve dados do banco local (fonte única)
    e não faz chamadas externas.
    """

    def test_existing_id_returns_200(self):
        """
        Quando o ID existe em licitacoes_cache, deve retornar 200 com os dados.
        """
        app = _make_app()
        app.dependency_overrides[get_current_user] = _auth_user
        pool = _MockPool([_SAMPLE_ROW_1])

        with patch("app.api.licitacoes.get_pool", new=AsyncMock(return_value=pool)):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/api/licitacoes/abc-001")

        assert resp.status_code == 200, (
            f"Esperava 200 para ID existente, recebeu {resp.status_code}: {resp.text}"
        )

    def test_existing_by_numero_returns_200(self):
        """
        Licitação pode ser encontrada pelo numeroControlePNCP (campo 'numero').
        """
        app = _make_app()
        app.dependency_overrides[get_current_user] = _auth_user
        pool = _MockPool([_SAMPLE_ROW_1])

        with patch("app.api.licitacoes.get_pool", new=AsyncMock(return_value=pool)):
            with TestClient(app, raise_server_exceptions=False) as client:
                # Busca via query param pncp= (número de controle PNCP)
                resp = client.get(
                    "/api/licitacoes/dummy-id",
                    params={"pncp": "00100000001202400001"},
                )

        assert resp.status_code == 200, (
            f"Esperava 200 ao buscar por numero PNCP, recebeu {resp.status_code}: {resp.text}"
        )


# ── 4. GET /licitacoes/{id} — ID inexistente → 404 sem chamadas externas ─────

class TestGetLicitacaoNotFound:
    """
    Verifica que um ID inexistente retorna 404 sem tentar PNCP nem dadosabertos.
    """

    def test_unknown_id_returns_404(self):
        """
        Quando o ID não existe em licitacoes_cache, deve retornar 404 Não encontrado.
        """
        app = _make_app()
        app.dependency_overrides[get_current_user] = _auth_user
        pool = _MockPool([])  # banco vazio

        with patch("app.api.licitacoes.get_pool", new=AsyncMock(return_value=pool)):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/api/licitacoes/id-que-nao-existe")

        assert resp.status_code == 404, (
            f"Esperava 404 para ID inexistente, recebeu {resp.status_code}: {resp.text}"
        )

    def test_404_does_not_call_httpx(self):
        """
        O caminho de 404 não deve tentar httpx (PNCP write API ou dadosabertos).
        """
        app = _make_app()
        app.dependency_overrides[get_current_user] = _auth_user
        pool = _MockPool([])

        with patch("app.api.licitacoes.get_pool", new=AsyncMock(return_value=pool)), \
             patch("httpx.AsyncClient") as mock_client_cls:
            with TestClient(app, raise_server_exceptions=False) as client:
                client.get("/api/licitacoes/id-inexistente")

        mock_client_cls.assert_not_called(), (
            "httpx.AsyncClient foi instanciado em um GET /licitacoes/{id} que "
            "resultou em 404 — a API não deve chamar APIs externas."
        )

    def test_404_detail_message(self):
        """Mensagem de detalhe do 404 deve ser legível."""
        app = _make_app()
        app.dependency_overrides[get_current_user] = _auth_user
        pool = _MockPool([])

        with patch("app.api.licitacoes.get_pool", new=AsyncMock(return_value=pool)):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/api/licitacoes/id-inexistente")

        body = resp.json()
        assert "detail" in body, f"Campo 'detail' ausente no 404: {body}"
        assert body["detail"], "Mensagem de detalhe do 404 está vazia"


# ── 5. GET /licitacoes nunca usa httpx ───────────────────────────────────────

class TestSearchNeverCallsExternalAPIs:
    """
    Garante que GET /licitacoes não instancia httpx.AsyncClient em nenhum
    cenário — o banco é a única fonte de dados.
    """

    def test_search_with_results_does_not_call_httpx(self):
        app = _make_app()
        app.dependency_overrides[get_current_user] = _auth_user

        with patch(
            "app.api.licitacoes.get_pool",
            new=AsyncMock(return_value=_MockPool([])),
        ), patch(
            "app.api.licitacoes.search_licitacoes_cache",
            new=AsyncMock(return_value=([_SAMPLE_ROW_1], 1)),
        ), patch("httpx.AsyncClient") as mock_cls:
            with TestClient(app, raise_server_exceptions=False) as client:
                client.get("/api/licitacoes")

        mock_cls.assert_not_called(), (
            "httpx.AsyncClient foi instanciado durante GET /licitacoes — "
            "a API deve servir apenas do banco local."
        )

    def test_search_empty_results_does_not_call_httpx(self):
        app = _make_app()
        app.dependency_overrides[get_current_user] = _auth_user

        with patch(
            "app.api.licitacoes.get_pool",
            new=AsyncMock(return_value=_MockPool([])),
        ), patch(
            "app.api.licitacoes.search_licitacoes_cache",
            new=AsyncMock(return_value=([], 0)),
        ), patch("httpx.AsyncClient") as mock_cls:
            with TestClient(app, raise_server_exceptions=False) as client:
                client.get("/api/licitacoes")

        mock_cls.assert_not_called(), (
            "httpx.AsyncClient foi instanciado mesmo com banco vazio — "
            "não deve haver fallback para APIs externas."
        )
