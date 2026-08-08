-- Schema do microsserviço collector
-- Executar uma vez no banco antes de rodar o collector.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Licitações normalizadas ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenders (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    source            VARCHAR(50) NOT NULL,          -- pncp | comprasnet | bec_sp | bbmnet
    external_id       VARCHAR(255) NOT NULL,
    numero_controle   VARCHAR(255),
    objeto            TEXT,
    orgao             VARCHAR(500),
    cnpj_orgao        VARCHAR(20),
    unidade           VARCHAR(500),
    uf                CHAR(2),
    municipio         VARCHAR(255),
    modalidade        VARCHAR(100),
    situacao          VARCHAR(100),
    valor_estimado    NUMERIC(15, 2),
    data_publicacao   DATE,
    data_abertura     TIMESTAMPTZ,
    data_encerramento TIMESTAMPTZ,
    srp               BOOLEAN DEFAULT FALSE,
    link_original     TEXT,
    dados_brutos      JSONB,
    criado_em         TIMESTAMPTZ DEFAULT NOW(),
    atualizado_em     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_tenders_uf         ON tenders (uf);
CREATE INDEX IF NOT EXISTS idx_tenders_modalidade  ON tenders (modalidade);
CREATE INDEX IF NOT EXISTS idx_tenders_situacao    ON tenders (situacao);
CREATE INDEX IF NOT EXISTS idx_tenders_publicacao  ON tenders (data_publicacao DESC);
CREATE INDEX IF NOT EXISTS idx_tenders_orgao       ON tenders (cnpj_orgao);

-- Índice para deduplicação cross-portal (objeto + orgao + data_publicacao)
CREATE INDEX IF NOT EXISTS idx_tenders_dedup
    ON tenders (objeto text_pattern_ops, orgao text_pattern_ops, data_publicacao)
    WHERE objeto IS NOT NULL AND orgao IS NOT NULL AND data_publicacao IS NOT NULL;

-- ── Itens das licitações ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tender_items (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id       UUID        NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    numero_item     INTEGER,
    descricao       TEXT,
    quantidade      NUMERIC(15, 4),
    unidade_medida  VARCHAR(100),
    valor_unitario  NUMERIC(15, 4),
    valor_total     NUMERIC(15, 4),
    criado_em       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tender_items_tender ON tender_items (tender_id);

-- ── Histórico de mudanças ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tender_history (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id      UUID        NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    campo          VARCHAR(255) NOT NULL,
    valor_anterior TEXT,
    valor_novo     TEXT,
    criado_em      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tender_history_tender ON tender_history (tender_id);
CREATE INDEX IF NOT EXISTS idx_tender_history_campo  ON tender_history (tender_id, campo);

-- ── Status do collector — uma linha por portal + "global" ──────────────────
CREATE TABLE IF NOT EXISTS collector_status (
    portal          TEXT        PRIMARY KEY,
    last_run        TIMESTAMPTZ,
    processed       INT         DEFAULT 0,
    errors          INT         DEFAULT 0,
    interval_hours  INT         DEFAULT 4,
    atualizado_em   TIMESTAMPTZ DEFAULT NOW()
);
