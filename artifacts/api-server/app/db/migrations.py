"""
migrations.py — DDL de bootstrap executado no startup da aplicação.

Usa CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS para ser idempotente
em qualquer ambiente (desenvolvimento, staging, produção, novo deploy).
Não depende de ferramentas externas (drizzle-kit, alembic).
"""
from __future__ import annotations

import logging
import asyncpg

logger = logging.getLogger(__name__)

# ── DDL statements — idempotentes ────────────────────────────────────────────

_DDL = [
    # Status global do sync — uma linha por janela canônica.
    # is_complete=FALSE quando a paginação foi truncada pelo cap máximo de páginas.
    """
    CREATE TABLE IF NOT EXISTS licitacoes_cache_coverage (
        scope_key   TEXT PRIMARY KEY,
        last_sync   TIMESTAMPTZ DEFAULT NOW(),
        total_found INT DEFAULT 0,
        is_complete BOOLEAN DEFAULT TRUE,
        window_days INT DEFAULT 30
    )
    """,
    # Colunas adicionadas após o CREATE — idempotentes via ADD COLUMN IF NOT EXISTS
    "ALTER TABLE licitacoes_cache_coverage ADD COLUMN IF NOT EXISTS is_complete BOOLEAN DEFAULT TRUE",
    "ALTER TABLE licitacoes_cache_coverage ADD COLUMN IF NOT EXISTS window_days INT DEFAULT 30",
    # Cache de licitações — tabela central desta migração
    """
    CREATE TABLE IF NOT EXISTS licitacoes_cache (
        numero              TEXT PRIMARY KEY,
        id                  TEXT,
        ano                 INT,
        objeto              TEXT,
        orgao_nome          TEXT,
        orgao_cnpj          TEXT,
        uf                  TEXT,
        municipio           TEXT,
        modalidade          TEXT,
        modalidade_codigo   INT,
        modo_disputa        TEXT,
        situacao            TEXT,
        valor_estimado      NUMERIC(18,2),
        data_publicacao     TIMESTAMPTZ,
        data_abertura       TIMESTAMPTZ,
        data_encerramento   TIMESTAMPTZ,
        esfera              TEXT,
        poder               TEXT,
        srp                 BOOLEAN DEFAULT FALSE,
        numero_processo     TEXT,
        informacao_complementar TEXT,
        amparo_legal        TEXT,
        raw_json            JSONB,
        fonte               TEXT DEFAULT 'pncp',
        criado_no_cache_em  TIMESTAMPTZ DEFAULT NOW(),
        atualizado_em       TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_lic_uf         ON licitacoes_cache(uf)",
    "CREATE INDEX IF NOT EXISTS idx_lic_modalidade ON licitacoes_cache(modalidade_codigo)",
    "CREATE INDEX IF NOT EXISTS idx_lic_situacao   ON licitacoes_cache(situacao)",
    "CREATE INDEX IF NOT EXISTS idx_lic_publicacao ON licitacoes_cache(data_publicacao DESC)",
    "CREATE INDEX IF NOT EXISTS idx_lic_atualizado ON licitacoes_cache(atualizado_em DESC)",
    """
    CREATE INDEX IF NOT EXISTS idx_lic_objeto_gin ON licitacoes_cache
        USING gin(to_tsvector('portuguese',
            coalesce(objeto,'') || ' ' || coalesce(orgao_nome,'')))
    """,
    # Coluna de link de navegação em alertas — aponta para a rota interna do app
    # (ex: /gerenciamento/{id} para alertas de tarefas).  Idempotente.
    "ALTER TABLE alertas ADD COLUMN IF NOT EXISTS link TEXT",
    # Backfill: preenche link para alertas de tarefas criados antes da coluna existir.
    # licitacao_id guarda 'tarefa_{id}' como chave de deduplicação — juntamos com
    # gerenciamento_tarefas para recuperar o gerenciamento_id correto.  Idempotente
    # (só atualiza onde link IS NULL e a tarefa ainda existe).
    """
    UPDATE alertas a
    SET    link = '/gerenciamento/' || t.gerenciamento_id
    FROM   gerenciamento_tarefas t
    WHERE  a.link IS NULL
      AND  a.licitacao_id = 'tarefa_' || t.id::text
    """,
    # Tabela de documentos de habilitação vinculados a um gerenciamento
    """
    CREATE TABLE IF NOT EXISTS gerenciamento_habilitacao (
        id                  SERIAL PRIMARY KEY,
        gerenciamento_id    INT NOT NULL REFERENCES licitacoes_gerenciadas(id) ON DELETE CASCADE,
        user_id             TEXT NOT NULL,
        documento           TEXT NOT NULL,
        status              TEXT NOT NULL DEFAULT 'pendente',
        observacoes         TEXT,
        data_entrega        DATE,
        criado_em           TIMESTAMPTZ DEFAULT NOW(),
        atualizado_em       TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_hab_gerenciamento ON gerenciamento_habilitacao(gerenciamento_id)",
    # Colunas de preferências de notificação em users — idempotentes
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS notif_email boolean NOT NULL DEFAULT true",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS notif_push boolean NOT NULL DEFAULT true",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS notif_whatsapp boolean NOT NULL DEFAULT false",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS notif_telegram boolean NOT NULL DEFAULT false",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_chat_id text",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone text",
    # Registro de execuções de jobs agendados — usado para detectar misfires no startup
    """
    CREATE TABLE IF NOT EXISTS job_runs (
        id          SERIAL PRIMARY KEY,
        job_name    TEXT NOT NULL,
        ran_at      TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_job_runs_name_ran ON job_runs(job_name, ran_at DESC)",
]


async def run_migrations(pool: asyncpg.Pool) -> bool:
    """
    Executa todas as migrações DDL em ordem. Seguro para rodar múltiplas vezes.
    Retorna True em sucesso, False em falha (e sinaliza o repo via set_cache_ready).
    """
    from .licitacoes_repo import set_cache_ready

    try:
        async with pool.acquire() as conn:
            for ddl in _DDL:
                stmt = ddl.strip()
                if not stmt:
                    continue
                await conn.execute(stmt)
    except Exception as exc:
        logger.error(
            "migrations: falha no DDL de bootstrap — cache de licitações desativado: %s", exc
        )
        set_cache_ready(False)
        return False

    set_cache_ready(True)
    logger.info("migrations: DDL de bootstrap concluído — cache de licitações ativo.")
    return True
