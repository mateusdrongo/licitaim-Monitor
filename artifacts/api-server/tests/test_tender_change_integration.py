"""
test_tender_change_integration.py

Testes de integração com banco real para o pipeline de detecção de mudanças
em licitações favoritadas:

  tender_history → check_favorited_tender_changes()
                 → notify_favorited_tender_changes()
                 → send_tender_update()  (escreve em alertas)
                 → snapshot atualizado em favoritos

Requer DATABASE_URL no ambiente (pula automaticamente se ausente).
Senders externos (email, Telegram) são mockados para evitar I/O externo.

Execução:
    PYTHONPATH=. pytest tests/test_tender_change_integration.py -v
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── skip ──────────────────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not DATABASE_URL:
    pytest.skip("DATABASE_URL não configurado", allow_module_level=True)

# ── DDL: garante tabelas do collector que podem não existir no schema da API ──

_DDL_TENDERS = """
CREATE TABLE IF NOT EXISTS tenders (
    id                UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    source            VARCHAR(50)   NOT NULL,
    external_id       VARCHAR(255)  NOT NULL,
    numero_controle   VARCHAR(255),
    objeto            TEXT,
    objeto_norm       TEXT,
    orgao             TEXT,
    orgao_norm        TEXT,
    cnpj_orgao        VARCHAR(20),
    unidade           TEXT,
    uf                VARCHAR(2),
    municipio         TEXT,
    modalidade        VARCHAR(100),
    situacao          VARCHAR(100),
    valor_estimado    NUMERIC(15, 2),
    data_publicacao   DATE,
    data_abertura     TIMESTAMP,
    data_encerramento TIMESTAMP,
    srp               BOOLEAN        DEFAULT FALSE,
    link_original     TEXT,
    dados_brutos      JSONB,
    criado_em         TIMESTAMPTZ    DEFAULT NOW(),
    atualizado_em     TIMESTAMPTZ    DEFAULT NOW(),
    UNIQUE(source, external_id)
)
"""

_DDL_TENDER_HISTORY = """
CREATE TABLE IF NOT EXISTS tender_history (
    id             UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id      UUID         NOT NULL,
    campo          VARCHAR(255) NOT NULL,
    valor_anterior TEXT,
    valor_novo     TEXT,
    criado_em      TIMESTAMPTZ  DEFAULT NOW()
)
"""


# ── helper: pool e dados de teste ─────────────────────────────────────────────

async def _make_pool():
    """Cria pool asyncpg e garante tabelas do collector."""
    import asyncpg
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)
    async with pool.acquire() as conn:
        await conn.execute(_DDL_TENDERS)
        await conn.execute(_DDL_TENDER_HISTORY)
    return pool


@asynccontextmanager
async def _test_data(pool):
    """
    Insere fixtures isolados por execução e limpa tudo no final.

    Cria:
      - 1 users row (notif_email=true)
      - 1 tenders row (situacao='encerrado')
      - 1 tender_history row (situacao: 'aberto' → 'encerrado')
      - 1 favoritos row (snapshot com situacao='aberto')
    """
    tag            = str(uuid.uuid4())[:8]
    user_id        = str(uuid.uuid4())
    tender_uuid    = uuid.uuid4()
    tender_uuid_str = str(tender_uuid)

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (id, email, nome, senha_hash, notif_email, notif_push)"
            " VALUES ($1, $2, $3, 'dummy', true, false) ON CONFLICT (id) DO NOTHING",
            user_id,
            f"int-test-{tag}@example.com",
            "Usuário Integração",
        )
        await conn.execute(
            "INSERT INTO tenders (id, source, external_id, objeto, situacao,"
            " valor_estimado, modalidade)"
            " VALUES ($1,'test',$2,'Aquisição de computadores','encerrado',150000.00,'Pregão')",
            tender_uuid,
            f"INT-TEST-{tag}",
        )
        await conn.execute(
            "INSERT INTO tender_history (tender_id, campo, valor_anterior, valor_novo)"
            " VALUES ($1,'situacao','aberto','encerrado')",
            tender_uuid,
        )
        fav_id = await conn.fetchval(
            "INSERT INTO favoritos (user_id, licitacao_id, licitacao_objeto,"
            " licitacao_situacao, licitacao_valor)"
            " VALUES ($1,$2,'Aquisição de computadores','aberto','100000.00')"
            " RETURNING id",
            user_id,
            tender_uuid_str,
        )

    try:
        yield {
            "user_id":        user_id,
            "tender_uuid":    tender_uuid_str,
            "tender_uuid_obj": tender_uuid,
            "fav_id":         fav_id,
        }
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM alertas      WHERE user_id   = $1", user_id)
            await conn.execute("DELETE FROM favoritos    WHERE user_id   = $1", user_id)
            await conn.execute("DELETE FROM tender_history WHERE tender_id = $1", tender_uuid)
            await conn.execute("DELETE FROM tenders      WHERE id        = $1", tender_uuid)
            await conn.execute("DELETE FROM users        WHERE id        = $1", user_id)
            # Remove cursor entries so they don't skew later tests
            await conn.execute(
                "DELETE FROM job_runs"
                " WHERE job_name = 'check_favorited_tender_changes'"
                " AND ran_at >= NOW() - INTERVAL '10 minutes'"
            )


def _patch_senders():
    """Silencia email e Telegram sem tocar na lógica de banco."""
    return [
        patch("app.services.senders.email_sender.send_email",    AsyncMock(return_value=True)),
        patch("app.services.senders.telegram_sender.send_telegram", AsyncMock(return_value=True)),
    ]


# ── testes ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_alert_row_created_in_alertas():
    """
    Após uma execução do job um alerta do tipo 'situacao_alterada' deve aparecer
    em `alertas` para o usuário que favoritou a licitação alterada.
    """
    from app.services.monitor_worker import check_favorited_tender_changes

    pool = await _make_pool()
    try:
        async with _test_data(pool) as ctx:
            patches = _patch_senders()
            for p in patches:
                p.start()
            try:
                with patch("app.db.session.get_pool", AsyncMock(return_value=pool)):
                    result = await check_favorited_tender_changes()
            finally:
                for p in patches:
                    p.stop()

            assert result["tenders_with_changes"] >= 1, (
                f"Esperado ≥1 tender com mudanças, obtido: {result}"
            )
            assert result["users_notified"] >= 1, (
                f"Esperado ≥1 usuário notificado, obtido: {result}"
            )

            async with pool.acquire() as conn:
                alerta = await conn.fetchrow(
                    "SELECT tipo FROM alertas"
                    " WHERE user_id = $1 ORDER BY criado_em DESC LIMIT 1",
                    ctx["user_id"],
                )

            assert alerta is not None, (
                "Nenhum alerta encontrado em `alertas` após execução do job."
            )
            assert alerta["tipo"] == "situacao_alterada", (
                f"Tipo de alerta inesperado: {alerta['tipo']!r}"
            )
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_favorito_snapshot_updated_after_job():
    """
    Após o job, licitacao_situacao em `favoritos` deve refletir o novo
    valor ('encerrado'), evitando re-notificação no próximo ciclo.
    """
    from app.services.monitor_worker import check_favorited_tender_changes

    pool = await _make_pool()
    try:
        async with _test_data(pool) as ctx:
            patches = _patch_senders()
            for p in patches:
                p.start()
            try:
                with patch("app.db.session.get_pool", AsyncMock(return_value=pool)):
                    await check_favorited_tender_changes()
            finally:
                for p in patches:
                    p.stop()

            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT licitacao_situacao FROM favoritos WHERE user_id = $1",
                    ctx["user_id"],
                )

            assert row is not None, "Favorito não encontrado após o job."
            assert row["licitacao_situacao"] == "encerrado", (
                f"Snapshot não atualizado: {row['licitacao_situacao']!r}"
                " (esperado 'encerrado')"
            )
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_no_double_notification_on_second_run():
    """
    Uma segunda execução imediata do job não deve gerar novo alerta —
    o snapshot foi atualizado na primeira execução.
    """
    from app.services.monitor_worker import check_favorited_tender_changes

    pool = await _make_pool()
    try:
        async with _test_data(pool) as ctx:
            patches = _patch_senders()
            for p in patches:
                p.start()
            try:
                with patch("app.db.session.get_pool", AsyncMock(return_value=pool)):
                    result1 = await check_favorited_tender_changes()

                # Conta alertas após o primeiro run
                async with pool.acquire() as conn:
                    count_after_first = await conn.fetchval(
                        "SELECT COUNT(*) FROM alertas WHERE user_id = $1",
                        ctx["user_id"],
                    )

                with patch("app.db.session.get_pool", AsyncMock(return_value=pool)):
                    await check_favorited_tender_changes()

                async with pool.acquire() as conn:
                    count_after_second = await conn.fetchval(
                        "SELECT COUNT(*) FROM alertas WHERE user_id = $1",
                        ctx["user_id"],
                    )
            finally:
                for p in patches:
                    p.stop()

            assert result1["users_notified"] >= 1, (
                f"Primeiro run deve notificar ≥1 usuário: {result1}"
            )
            assert count_after_second == count_after_first, (
                f"Segundo run gerou alertas extras: "
                f"{count_after_second} vs {count_after_first}"
            )
    finally:
        await pool.close()
