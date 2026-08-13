"""
test_licitacoes_cache_integration.py — Testes de integração: ciclo coletor → busca.

Verifica o contrato end-to-end da arquitetura collector-first usando o banco
real (DATABASE_URL) e as funções de produção:

  upsert_to_licitacoes_cache()  ← collector/app/cache_writer.py
       ↓
  search_licitacoes_cache()     ← artifacts/api-server/app/db/licitacoes_repo.py
       ↓
  GET /api/licitacoes           ← artifacts/api-server/app/api/licitacoes.py

Cada teste limpa as linhas de teste ao final (DELETE WHERE numero = LIKE 'integ-test-%')
para não sujar o banco de dados.

Cobertura mínima exigida pela tarefa:
  1. licitação inserida via upsert aparece em search_licitacoes_cache (camada repo).
  2. licitação inserida via upsert aparece em GET /api/licitacoes (camada HTTP).
  3. GET /api/licitacoes/{id} retorna 404 para ID inexistente — sem fallback externo.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
import asyncpg
import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from app.main import app
from app.core import deps as _deps_mod
from app.db import licitacoes_repo
from app.db.licitacoes_repo import search_licitacoes_cache, set_cache_ready

# Collector's production persistence path (the path the real collector uses)
from collector.app.cache_writer import upsert_to_licitacoes_cache


# ── Helpers ───────────────────────────────────────────────────────────────────

def _db_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        pytest.skip("DATABASE_URL não configurado — pulando testes de integração com DB real")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def _test_numero() -> str:
    """Gera um numero único para o teste, prefixado para fácil limpeza."""
    return f"integ-test-{uuid.uuid4().hex[:12]}"


def _tender_hoje(numero: str) -> dict:
    """
    Tender normalizado com data_publicacao = hoje, usando o mesmo formato ISO
    que o scraper PNCP produz (ex: '2026-08-13T00:00:00'), dentro da janela
    de 30 dias que o endpoint usa por padrão (hoje - 30d → hoje).

    Usa strings ISO propositalmente para exercitar o caminho real de
    cache_writer._parse_ts(), que foi corrigido para não fatiar pela largura
    do token de formato (len('%Y-%m-%d') == 8, não 10).
    """
    hoje_iso = date.today().isoformat() + "T00:00:00"   # formato PNCP real
    return {
        "numero_controle": numero,
        "external_id":     numero,
        "objeto":          "Aquisição de material de teste de integração automatizado",
        "orgao":           "Órgão de Testes Automatizados",
        "orgao_cnpj":      "00000000000191",
        "uf":              "SP",
        "municipio":       "São Paulo",
        "modalidade":      "Pregão Eletrônico",
        "modo_disputa":    "Aberto",
        "situacao":        "aberta",
        "valor_estimado":  12345.67,
        "data_publicacao": hoje_iso,   # string ISO — formato real do scraper PNCP
        "data_abertura":   hoje_iso,
        "esfera":          "federal",
        "poder":           "executivo",
        "srp":             False,
    }


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_pool():
    """Pool asyncpg apontando para o banco real; fecha ao fim do teste."""
    pool = await asyncpg.create_pool(_db_url(), min_size=1, max_size=3)
    yield pool
    await pool.close()


@pytest.fixture(autouse=True)
def _cache_ready():
    """Ativa _cache_ready=True durante cada teste e restaura ao final."""
    set_cache_ready(True)
    yield
    set_cache_ready(False)


_FAKE_USER = {"id": "u-integ-test", "nome": "Tester", "email": "tester@example.com"}


# ── Testes ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upserted_tender_appears_in_search_licitacoes_cache(db_pool):
    """
    Camada de repositório:
    Após chamar upsert_to_licitacoes_cache (caminho de produção do coletor),
    search_licitacoes_cache deve retornar a licitação inserida.
    """
    numero = _test_numero()
    tender = _tender_hoje(numero)

    try:
        # ── Etapa 1: inserir via a função de persistência do coletor ─────────
        result = await upsert_to_licitacoes_cache(db_pool, [tender], fonte="integ-test")
        inseridos = result[0]
        assert inseridos == 1, (
            f"Esperado 1 linha inserida, obteve {inseridos}. "
            "Verifique upsert_to_licitacoes_cache."
        )

        # ── Etapa 2: buscar via camada de repositório ─────────────────────────
        hoje = date.today().isoformat()
        data_ini = (date.today() - timedelta(days=1)).isoformat()
        items, total = await search_licitacoes_cache(
            db_pool,
            q="material de teste de integração",
            data_inicio=data_ini,
            data_fim=hoje,
        )

        assert total >= 1, (
            "search_licitacoes_cache retornou total=0 após upsert — "
            "a licitação inserida não está sendo encontrada pelo repositório."
        )
        numeros = [item["numero"] for item in items]
        assert numero in numeros, (
            f"Número '{numero}' não encontrado nos resultados do repositório.\n"
            f"Números retornados: {numeros}"
        )

    finally:
        # Limpeza: remove linha de teste para não poluir o banco
        await db_pool.execute(
            "DELETE FROM licitacoes_cache WHERE numero = $1", numero
        )


@pytest.mark.asyncio
async def test_upserted_tender_appears_in_http_search(db_pool):
    """
    Camada HTTP (end-to-end):
    Após chamar upsert_to_licitacoes_cache, GET /api/licitacoes deve retornar
    a licitação com source='banco', confirmando a cadeia completa.
    """
    from unittest.mock import AsyncMock, patch

    numero = _test_numero()
    tender = _tender_hoje(numero)

    try:
        # ── Etapa 1: inserir via coletor ──────────────────────────────────────
        result = await upsert_to_licitacoes_cache(db_pool, [tender], fonte="integ-test")
        assert result[0] == 1, f"Upsert não inseriu a linha: resultado={result}"

        # ── Etapa 2: chamar GET /api/licitacoes com o pool real ───────────────
        mock_get_pool = AsyncMock(return_value=db_pool)
        app.dependency_overrides[_deps_mod.get_current_user] = lambda: _FAKE_USER

        try:
            with patch("app.api.licitacoes.get_pool", mock_get_pool):
                hoje = date.today().isoformat()
                data_ini = (date.today() - timedelta(days=1)).isoformat()
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    resp = await client.get(
                        "/api/licitacoes",
                        params={
                            "q": "material de teste de integração",
                            "dataInicio": data_ini,
                            "dataFim": hoje,
                        },
                    )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, (
            f"Esperado 200, recebido {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert body["source"] == "banco", (
            "O endpoint deve servir exclusivamente do banco local (collector-first); "
            f"source retornado: {body.get('source')!r}"
        )
        assert body["total"] >= 1, (
            "total=0 — a licitação inserida via coletor não apareceu em GET /licitacoes."
        )
        numeros = [item.get("numero") for item in body["data"]]
        assert numero in numeros, (
            f"Número '{numero}' não encontrado na resposta HTTP.\n"
            f"Números retornados: {numeros}"
        )

    finally:
        await db_pool.execute(
            "DELETE FROM licitacoes_cache WHERE numero = $1", numero
        )


@pytest.mark.asyncio
async def test_get_licitacao_by_id_returns_404_for_nonexistent(db_pool):
    """
    GET /api/licitacoes/{id} deve retornar 404 para um ID que não existe no banco,
    sem tentar chamar APIs externas (arquitetura collector-first: sem fallback).

    O ID usado não coincide com nenhuma linha real nem com os MOCK_LICITACOES
    hardcoded no endpoint (que têm formato CNPJ14-unit-seq/ano e '/' no nome).
    """
    from unittest.mock import AsyncMock, patch

    id_inexistente = "integ-test-id-inexistente-xyz-sem-barra"

    mock_get_pool = AsyncMock(return_value=db_pool)
    app.dependency_overrides[_deps_mod.get_current_user] = lambda: _FAKE_USER

    try:
        with patch("app.api.licitacoes.get_pool", mock_get_pool):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.get(f"/api/licitacoes/{id_inexistente}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404, (
        f"Esperado 404 para ID inexistente, recebido {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert "detail" in body, "Resposta 404 deve ter campo 'detail'"
    assert body["detail"], "Campo 'detail' não pode ser vazio"
