"""
migrations.py — DDL de bootstrap executado no startup da aplicação.

Usa CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS para ser idempotente
em qualquer ambiente (desenvolvimento, staging, produção, novo deploy).
Não depende de ferramentas externas (drizzle-kit, alembic).

Ordem de execução respeita dependências entre tabelas (FK ordering):
  users → monitoramentos → alertas
  users → favoritos
  users → agenda_eventos
  users → notifications
  licitacoes_gerenciadas → gerenciamento_tarefas
  licitacoes_gerenciadas → gerenciamento_anotacoes
  licitacoes_gerenciadas → gerenciamento_habilitacao
"""
from __future__ import annotations

import logging
import asyncpg

logger = logging.getLogger(__name__)

# ── DDL statements — idempotentes ────────────────────────────────────────────

_DDL = [
    # ── 1. Tabela raiz: usuários ──────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS users (
        id            TEXT PRIMARY KEY,
        nome          TEXT NOT NULL,
        email         VARCHAR(255) NOT NULL UNIQUE,
        senha_hash    TEXT,
        empresa       TEXT,
        cnpj          VARCHAR(18),
        plano         VARCHAR(20) NOT NULL DEFAULT 'gratuito',
        avatar_url    TEXT,
        criado_em     TIMESTAMP NOT NULL DEFAULT NOW(),
        atualizado_em TIMESTAMP NOT NULL DEFAULT NOW()
    )
    """,
    # Colunas de notificação adicionadas após o schema inicial
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS notif_email     BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS notif_push      BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS notif_whatsapp  BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS notif_telegram  BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_chat_id TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone           TEXT",

    # ── 2. Monitoramentos — depende de users ──────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS monitoramentos (
        id               SERIAL PRIMARY KEY,
        user_id          TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        nome             TEXT NOT NULL,
        ativo            BOOLEAN NOT NULL DEFAULT TRUE,
        palavras_chave   TEXT NOT NULL DEFAULT '',
        modalidades      TEXT NOT NULL DEFAULT '',
        ufs              TEXT NOT NULL DEFAULT '',
        esferas          TEXT NOT NULL DEFAULT '',
        valor_min        TEXT,
        valor_max        TEXT,
        total_alertas    INTEGER NOT NULL DEFAULT 0,
        ultima_execucao  TIMESTAMP,
        criado_em        TIMESTAMP NOT NULL DEFAULT NOW(),
        atualizado_em    TIMESTAMP NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_mon_user ON monitoramentos(user_id)",

    # ── 3. Alertas — depende de users e monitoramentos ────────────────────────
    """
    CREATE TABLE IF NOT EXISTS alertas (
        id                SERIAL PRIMARY KEY,
        user_id           TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        monitoramento_id  INTEGER REFERENCES monitoramentos(id) ON DELETE SET NULL,
        tipo              TEXT NOT NULL,
        titulo            TEXT NOT NULL,
        descricao         TEXT NOT NULL DEFAULT '',
        lido              BOOLEAN NOT NULL DEFAULT FALSE,
        licitacao_id      TEXT,
        licitacao_objeto  TEXT,
        monitoramento_nome TEXT,
        criado_em         TIMESTAMP NOT NULL DEFAULT NOW(),
        link              TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ale_user_lido ON alertas(user_id, lido)",
    "CREATE INDEX IF NOT EXISTS idx_ale_criado    ON alertas(criado_em DESC)",
    # Coluna link adicionada após o schema inicial — idempotente
    "ALTER TABLE alertas ADD COLUMN IF NOT EXISTS link TEXT",

    # ── 4. Favoritos — depende de users ──────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS favoritos (
        id                   SERIAL PRIMARY KEY,
        user_id              TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        licitacao_id         TEXT NOT NULL,
        nota                 TEXT,
        licitacao_objeto     TEXT,
        licitacao_orgao      TEXT,
        licitacao_uf         TEXT,
        licitacao_modalidade TEXT,
        licitacao_situacao   TEXT,
        licitacao_valor      TEXT,
        criado_em            TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE(user_id, licitacao_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_fav_user ON favoritos(user_id)",

    # ── 5. Cache de licitações — sem deps ────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS licitacoes_cache_coverage (
        scope_key   TEXT PRIMARY KEY,
        last_sync   TIMESTAMPTZ DEFAULT NOW(),
        total_found INT DEFAULT 0,
        is_complete BOOLEAN DEFAULT TRUE,
        window_days INT DEFAULT 30
    )
    """,
    "ALTER TABLE licitacoes_cache_coverage ADD COLUMN IF NOT EXISTS is_complete BOOLEAN DEFAULT TRUE",
    "ALTER TABLE licitacoes_cache_coverage ADD COLUMN IF NOT EXISTS window_days INT DEFAULT 30",
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

    # ── 6. Licitações gerenciadas — sem deps (user_id é texto livre, sem FK) ─
    """
    CREATE TABLE IF NOT EXISTS licitacoes_gerenciadas (
        id                          SERIAL PRIMARY KEY,
        user_id                     TEXT NOT NULL,
        licitacao_id                TEXT NOT NULL,
        licitacao_numero            TEXT,
        licitacao_objeto            TEXT,
        licitacao_orgao             TEXT,
        licitacao_cnpj              TEXT,
        licitacao_uf                TEXT,
        licitacao_municipio         TEXT,
        licitacao_modalidade        TEXT,
        licitacao_situacao          TEXT,
        licitacao_valor             NUMERIC,
        licitacao_data_abertura     DATE,
        licitacao_data_encerramento DATE,
        licitacao_data_publicacao   DATE,
        licitacao_link_pncp         TEXT,
        status                      TEXT NOT NULL DEFAULT 'em_andamento',
        notas_gerais                TEXT,
        responsavel                 TEXT,
        resultado                   TEXT,
        valor_proposta              NUMERIC,
        criado_em                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        atualizado_em               TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_lic_ger_user_lic ON licitacoes_gerenciadas(user_id, licitacao_id)",

    # ── 7. Tarefas — depende de licitacoes_gerenciadas ───────────────────────
    """
    CREATE TABLE IF NOT EXISTS gerenciamento_tarefas (
        id                  SERIAL PRIMARY KEY,
        gerenciamento_id    INT NOT NULL REFERENCES licitacoes_gerenciadas(id) ON DELETE CASCADE,
        user_id             TEXT NOT NULL DEFAULT '',
        titulo              TEXT NOT NULL,
        descricao           TEXT,
        prazo               DATE,
        prioridade          TEXT NOT NULL DEFAULT 'normal',
        categoria           TEXT NOT NULL DEFAULT 'geral',
        concluida           BOOLEAN NOT NULL DEFAULT FALSE,
        concluida_em        TIMESTAMPTZ,
        criado_em           TIMESTAMPTZ DEFAULT NOW(),
        atualizado_em       TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    # user_id pode estar ausente em tabelas criadas antes desta migração
    "ALTER TABLE gerenciamento_tarefas ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT ''",
    "CREATE INDEX IF NOT EXISTS idx_tar_gerenciamento ON gerenciamento_tarefas(gerenciamento_id)",

    # ── 8. Backfill de links em alertas — após tarefas existir ───────────────
    # licitacao_id guarda 'tarefa_{id}' como chave de deduplicação.
    # Só atualiza onde link IS NULL e a tarefa ainda existe — idempotente.
    """
    UPDATE alertas a
    SET    link = '/gerenciamento/' || t.gerenciamento_id
    FROM   gerenciamento_tarefas t
    WHERE  a.link IS NULL
      AND  a.licitacao_id = 'tarefa_' || t.id::text
    """,

    # ── 9. Anotações — depende de licitacoes_gerenciadas ─────────────────────
    """
    CREATE TABLE IF NOT EXISTS gerenciamento_anotacoes (
        id                SERIAL PRIMARY KEY,
        gerenciamento_id  INT NOT NULL REFERENCES licitacoes_gerenciadas(id) ON DELETE CASCADE,
        user_id           TEXT NOT NULL DEFAULT '',
        conteudo          TEXT NOT NULL,
        criado_em         TIMESTAMPTZ DEFAULT NOW(),
        atualizado_em     TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    # user_id pode estar ausente em tabelas criadas antes desta migração
    "ALTER TABLE gerenciamento_anotacoes ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT ''",
    "CREATE INDEX IF NOT EXISTS idx_ano_gerenciamento ON gerenciamento_anotacoes(gerenciamento_id)",

    # ── 10. Habilitação — depende de licitacoes_gerenciadas ──────────────────
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

    # ── 11. Agenda e notificações — dependem de users ─────────────────────────
    """
    CREATE TABLE IF NOT EXISTS agenda_eventos (
        id          SERIAL PRIMARY KEY,
        user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        titulo      TEXT NOT NULL,
        descricao   TEXT,
        data        DATE NOT NULL,
        observacao  TEXT,
        criado_em   TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_agenda_user_data ON agenda_eventos(user_id, data)",
    """
    CREATE TABLE IF NOT EXISTS notifications (
        id          SERIAL PRIMARY KEY,
        user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title       TEXT NOT NULL,
        body        TEXT NOT NULL DEFAULT '',
        tipo        TEXT NOT NULL DEFAULT 'geral',
        channel     TEXT NOT NULL DEFAULT 'push',
        lida        BOOLEAN NOT NULL DEFAULT FALSE,
        metadata    JSONB,
        criado_em   TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_notif_user_lida ON notifications(user_id, lida)",
    "CREATE INDEX IF NOT EXISTS idx_notif_criado    ON notifications(criado_em DESC)",

    # ── 12. Infraestrutura: jobs e collector ──────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS job_runs (
        id        SERIAL PRIMARY KEY,
        job_name  TEXT NOT NULL,
        ran_at    TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_job_runs_name_ran ON job_runs(job_name, ran_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS collector_status (
        portal          TEXT PRIMARY KEY,
        last_run        TIMESTAMPTZ,
        processed       INT DEFAULT 0,
        errors          INT DEFAULT 0,
        interval_hours  INT DEFAULT 4,
        atualizado_em   TIMESTAMPTZ DEFAULT NOW()
    )
    """,

    # ── 13. Collector alert state ─────────────────────────────────────────────
    # Single-row table (id=1) that tracks whether an outage alert has already
    # been sent for the current stale window, to avoid repeat notifications.
    """
    CREATE TABLE IF NOT EXISTS collector_alert_state (
        id                  INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
        is_stale_alerted    BOOLEAN NOT NULL DEFAULT FALSE,
        alerted_at          TIMESTAMPTZ,
        recovered_at        TIMESTAMPTZ
    )
    """,
    # Seed the single row if it doesn't exist yet
    """
    INSERT INTO collector_alert_state (id, is_stale_alerted)
    VALUES (1, FALSE)
    ON CONFLICT (id) DO NOTHING
    """,
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
