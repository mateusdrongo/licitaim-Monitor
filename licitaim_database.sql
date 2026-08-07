-- =============================================================================
--  LicitAIM — Schema PostgreSQL completo
--  Gerado em: 2026-07-16
--  Compatível com: PostgreSQL 14+
--
--  Ordem de execução:
--    1. Extensions
--    2. Tipos / Domínios
--    3. Tabelas (respeitando dependências FK)
--    4. Índices complementares
--    5. Funções auxiliares
--    6. Triggers
--    7. Views
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 0. CONFIGURAÇÕES DE SESSÃO
-- ---------------------------------------------------------------------------
SET client_encoding = 'UTF8';
SET standard_conforming_strings = ON;
SET check_function_bodies = TRUE;
SET client_min_messages = WARNING;

-- ---------------------------------------------------------------------------
-- 1. EXTENSIONS
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- índices GIN para busca de texto (ILIKE rápido)

-- ---------------------------------------------------------------------------
-- 2. TABELA: session  (connect-pg-simple / express-session)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "session" (
    sid     VARCHAR        NOT NULL PRIMARY KEY,
    sess    JSON           NOT NULL,
    expire  TIMESTAMP(6)   NOT NULL
);

CREATE INDEX IF NOT EXISTS "IDX_session_expire"
    ON "session" (expire);

-- ---------------------------------------------------------------------------
-- 3. TABELA: users
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            TEXT                        PRIMARY KEY,   -- UUID gerado na aplicação
    nome          TEXT                        NOT NULL,
    email         VARCHAR(255)                NOT NULL UNIQUE,
    senha_hash    TEXT,
    empresa       TEXT,
    cnpj          VARCHAR(20),
    plano         VARCHAR(20)                 NOT NULL DEFAULT 'gratuito',
                                                       -- gratuito | starter | profissional | enterprise
    avatar_url    TEXT,
    criado_em     TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_users_plano CHECK (
        plano IN ('gratuito', 'starter', 'profissional', 'enterprise')
    )
);

-- Índices de users
CREATE INDEX IF NOT EXISTS idx_users_email
    ON users (email);

CREATE INDEX IF NOT EXISTS idx_users_cnpj
    ON users (cnpj)
    WHERE cnpj IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_users_plano
    ON users (plano);

-- ---------------------------------------------------------------------------
-- 4. TABELA: monitoramentos
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS monitoramentos (
    id              SERIAL                      PRIMARY KEY,
    user_id         TEXT                        NOT NULL
                        REFERENCES users (id) ON DELETE CASCADE,
    nome            TEXT                        NOT NULL,
    ativo           BOOLEAN                     NOT NULL DEFAULT TRUE,
    palavras_chave  TEXT                        NOT NULL DEFAULT '[]',   -- JSON array
    modalidades     TEXT                        NOT NULL DEFAULT '[]',   -- JSON array
    ufs             TEXT                        NOT NULL DEFAULT '[]',   -- JSON array
    esferas         TEXT                        NOT NULL DEFAULT '[]',   -- JSON array
    valor_min       TEXT,   -- armazenado como texto para evitar imprecisão float
    valor_max       TEXT,
    total_alertas   INTEGER                     NOT NULL DEFAULT 0,
    ultima_execucao TIMESTAMP WITHOUT TIME ZONE,
    criado_em       TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

-- Índices de monitoramentos
CREATE INDEX IF NOT EXISTS idx_monitoramentos_user_id
    ON monitoramentos (user_id);

CREATE INDEX IF NOT EXISTS idx_monitoramentos_ativo
    ON monitoramentos (user_id, ativo);

-- ---------------------------------------------------------------------------
-- 5. TABELA: alertas
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alertas (
    id                  SERIAL                      PRIMARY KEY,
    user_id             TEXT                        NOT NULL
                            REFERENCES users (id) ON DELETE CASCADE,
    monitoramento_id    INTEGER
                            REFERENCES monitoramentos (id) ON DELETE SET NULL,
    tipo                TEXT                        NOT NULL,
                        -- nova_licitacao | prazo_vencendo | situacao_alterada
                        -- nova_disputa   | preco_referencia
    titulo              TEXT                        NOT NULL,
    descricao           TEXT                        NOT NULL,
    lido                BOOLEAN                     NOT NULL DEFAULT FALSE,
    licitacao_id        TEXT,
    licitacao_objeto    TEXT,
    monitoramento_nome  TEXT,
    criado_em           TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_alertas_tipo CHECK (
        tipo IN ('nova_licitacao', 'prazo_vencendo', 'situacao_alterada',
                 'nova_disputa', 'preco_referencia')
    )
);

-- Índices de alertas
CREATE INDEX IF NOT EXISTS idx_alertas_user_id
    ON alertas (user_id);

CREATE INDEX IF NOT EXISTS idx_alertas_user_lido
    ON alertas (user_id, lido);

CREATE INDEX IF NOT EXISTS idx_alertas_monitoramento_id
    ON alertas (monitoramento_id)
    WHERE monitoramento_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_alertas_criado_em
    ON alertas (criado_em DESC);

CREATE INDEX IF NOT EXISTS idx_alertas_licitacao_id
    ON alertas (licitacao_id)
    WHERE licitacao_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 6. TABELA: favoritos
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS favoritos (
    id                  SERIAL                      PRIMARY KEY,
    user_id             TEXT                        NOT NULL
                            REFERENCES users (id) ON DELETE CASCADE,
    licitacao_id        TEXT                        NOT NULL,
    nota                TEXT,
    -- Snapshot da licitação para exibição sem JOIN externo
    licitacao_objeto    TEXT,
    licitacao_orgao     TEXT,
    licitacao_uf        TEXT,
    licitacao_modalidade TEXT,
    licitacao_situacao  TEXT,
    licitacao_valor     TEXT,
    criado_em           TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_favoritos_user_licitacao UNIQUE (user_id, licitacao_id)
);

-- Índices de favoritos
CREATE INDEX IF NOT EXISTS idx_favoritos_user_id
    ON favoritos (user_id);

-- Índice GIN para busca de texto no objeto da licitação favoritada
CREATE INDEX IF NOT EXISTS idx_favoritos_objeto_trgm
    ON favoritos USING GIN (licitacao_objeto gin_trgm_ops)
    WHERE licitacao_objeto IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 7. TABELA: oportunidades  (pipeline comercial)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS oportunidades (
    id               SERIAL                      PRIMARY KEY,
    user_id          TEXT                        NOT NULL
                         REFERENCES users (id) ON DELETE CASCADE,
    titulo           TEXT                        NOT NULL,
    estagio          TEXT                        NOT NULL DEFAULT 'identificada',
                     -- identificada | qualificada | proposta | disputa | ganhou | perdeu
    valor_estimado   TEXT,   -- armazenado como texto
    probabilidade    INTEGER CHECK (probabilidade BETWEEN 0 AND 100),
    licitacao_id     TEXT,
    licitacao_objeto TEXT,
    responsavel_nome TEXT,
    responsavel_id   INTEGER,
    prazo            TEXT,   -- ISO date string (YYYY-MM-DD)
    notas            TEXT,
    tags             TEXT                        NOT NULL DEFAULT '[]',   -- JSON array
    criado_em        TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    atualizado_em    TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_oportunidades_estagio CHECK (
        estagio IN ('identificada', 'qualificada', 'proposta',
                    'disputa', 'ganhou', 'perdeu')
    )
);

-- Índices de oportunidades
CREATE INDEX IF NOT EXISTS idx_oportunidades_user_id
    ON oportunidades (user_id);

CREATE INDEX IF NOT EXISTS idx_oportunidades_estagio
    ON oportunidades (user_id, estagio);

CREATE INDEX IF NOT EXISTS idx_oportunidades_prazo
    ON oportunidades (prazo)
    WHERE prazo IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_oportunidades_licitacao_id
    ON oportunidades (licitacao_id)
    WHERE licitacao_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 8. TABELA: documentos
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documentos (
    id               SERIAL                      PRIMARY KEY,
    user_id          TEXT                        NOT NULL
                         REFERENCES users (id) ON DELETE CASCADE,
    nome             TEXT                        NOT NULL,
    categoria        TEXT                        NOT NULL DEFAULT 'outro',
                     -- edital | proposta | habilitacao | recurso | contrato | outro
    licitacao_id     TEXT,
    licitacao_objeto TEXT,
    url              TEXT,
    tamanho          INTEGER,   -- bytes
    tipo             TEXT,      -- MIME type
    descricao        TEXT,
    criado_em        TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    atualizado_em    TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_documentos_categoria CHECK (
        categoria IN ('edital', 'proposta', 'habilitacao',
                      'recurso', 'contrato', 'outro')
    )
);

-- Índices de documentos
CREATE INDEX IF NOT EXISTS idx_documentos_user_id
    ON documentos (user_id);

CREATE INDEX IF NOT EXISTS idx_documentos_categoria
    ON documentos (user_id, categoria);

CREATE INDEX IF NOT EXISTS idx_documentos_licitacao_id
    ON documentos (licitacao_id)
    WHERE licitacao_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_documentos_nome_trgm
    ON documentos USING GIN (nome gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- 9. TABELA: equipe_membros
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS equipe_membros (
    id            SERIAL                      PRIMARY KEY,
    owner_id      TEXT                        NOT NULL
                      REFERENCES users (id) ON DELETE CASCADE,
    member_id     TEXT
                      REFERENCES users (id) ON DELETE SET NULL,
    nome          TEXT                        NOT NULL,
    email         TEXT                        NOT NULL,
    papel         TEXT                        NOT NULL DEFAULT 'visualizador',
                  -- admin | editor | visualizador
    status        TEXT                        NOT NULL DEFAULT 'pendente',
                  -- ativo | pendente | inativo
    avatar_url    TEXT,
    criado_em     TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_equipe_papel   CHECK (papel   IN ('admin', 'editor', 'visualizador')),
    CONSTRAINT chk_equipe_status  CHECK (status  IN ('ativo', 'pendente', 'inativo')),
    CONSTRAINT uq_equipe_owner_email UNIQUE (owner_id, email)
);

-- Índices de equipe_membros
CREATE INDEX IF NOT EXISTS idx_equipe_owner_id
    ON equipe_membros (owner_id);

CREATE INDEX IF NOT EXISTS idx_equipe_member_id
    ON equipe_membros (member_id)
    WHERE member_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_equipe_status
    ON equipe_membros (owner_id, status);

-- ---------------------------------------------------------------------------
-- 10. TABELA: certidoes  (compliance / documentos legais com validade)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS certidoes (
    id               SERIAL                      PRIMARY KEY,
    user_id          TEXT                        NOT NULL
                         REFERENCES users (id) ON DELETE CASCADE,
    nome             TEXT                        NOT NULL,
    tipo             TEXT                        NOT NULL DEFAULT 'outro',
                     -- receita_federal | fgts | trabalhista | inss
                     -- estadual | municipal | contrato_social | outro
    orgao_emissor    TEXT,
    numero           TEXT,
    data_emissao     DATE,
    data_vencimento  DATE,
    descricao        TEXT,
    criado_em        TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    atualizado_em    TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_certidoes_tipo CHECK (
        tipo IN ('receita_federal', 'fgts', 'trabalhista', 'inss',
                 'estadual', 'municipal', 'contrato_social', 'outro')
    ),
    CONSTRAINT chk_certidoes_datas CHECK (
        data_vencimento IS NULL OR data_emissao IS NULL
        OR data_vencimento >= data_emissao
    )
);

-- Índices de certidoes
CREATE INDEX IF NOT EXISTS idx_certidoes_user_id
    ON certidoes (user_id);

CREATE INDEX IF NOT EXISTS idx_certidoes_tipo
    ON certidoes (user_id, tipo);

CREATE INDEX IF NOT EXISTS idx_certidoes_vencimento
    ON certidoes (data_vencimento)
    WHERE data_vencimento IS NOT NULL;

-- Índice parcial para buscas rápidas de certidões próximas do vencimento
CREATE INDEX IF NOT EXISTS idx_certidoes_vencimento_usuario
    ON certidoes (user_id, data_vencimento)
    WHERE data_vencimento IS NOT NULL;

-- =============================================================================
-- FUNÇÕES AUXILIARES
-- =============================================================================

-- ---------------------------------------------------------------------------
-- fn_set_atualizado_em()
--   Trigger function: atualiza automaticamente a coluna `atualizado_em`
--   em qualquer UPDATE. Aplica-se a todas as tabelas com esse campo.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_set_atualizado_em()
RETURNS TRIGGER
LANGUAGE plpgsql AS
$$
BEGIN
    NEW.atualizado_em := NOW();
    RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------
-- fn_incrementar_total_alertas()
--   Trigger function: incrementa monitoramentos.total_alertas sempre que
--   um alerta novo for inserido vinculado a um monitoramento.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_incrementar_total_alertas()
RETURNS TRIGGER
LANGUAGE plpgsql AS
$$
BEGIN
    IF NEW.monitoramento_id IS NOT NULL THEN
        UPDATE monitoramentos
           SET total_alertas   = total_alertas + 1,
               atualizado_em   = NOW()
         WHERE id = NEW.monitoramento_id;
    END IF;
    RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------
-- fn_decrementar_total_alertas()
--   Trigger function: decrementa monitoramentos.total_alertas quando um
--   alerta vinculado for excluído (garante contador sempre consistente).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_decrementar_total_alertas()
RETURNS TRIGGER
LANGUAGE plpgsql AS
$$
BEGIN
    IF OLD.monitoramento_id IS NOT NULL THEN
        UPDATE monitoramentos
           SET total_alertas   = GREATEST(0, total_alertas - 1),
               atualizado_em   = NOW()
         WHERE id = OLD.monitoramento_id;
    END IF;
    RETURN OLD;
END;
$$;

-- ---------------------------------------------------------------------------
-- fn_status_certidao(data_vencimento DATE)
--   Retorna o status calculado de uma certidão:
--     'vencida'   — vencimento já passou
--     'a_vencer'  — vence nos próximos 30 dias
--     'ativa'     — vence em mais de 30 dias
--     'sem_prazo' — sem data de vencimento cadastrada
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_status_certidao(p_data_vencimento DATE)
RETURNS TEXT
LANGUAGE plpgsql
STABLE AS
$$
BEGIN
    IF p_data_vencimento IS NULL THEN
        RETURN 'sem_prazo';
    END IF;

    IF p_data_vencimento < CURRENT_DATE THEN
        RETURN 'vencida';
    ELSIF p_data_vencimento <= CURRENT_DATE + INTERVAL '30 days' THEN
        RETURN 'a_vencer';
    ELSE
        RETURN 'ativa';
    END IF;
END;
$$;

-- ---------------------------------------------------------------------------
-- fn_dias_para_vencer(data_vencimento DATE)
--   Retorna o número de dias até o vencimento (negativo = já venceu).
--   NULL se sem data de vencimento.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_dias_para_vencer(p_data_vencimento DATE)
RETURNS INTEGER
LANGUAGE plpgsql
STABLE AS
$$
BEGIN
    IF p_data_vencimento IS NULL THEN
        RETURN NULL;
    END IF;
    RETURN (p_data_vencimento - CURRENT_DATE)::INTEGER;
END;
$$;

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Triggers de atualizado_em (SET BEFORE UPDATE em cada tabela)
-- ---------------------------------------------------------------------------

-- users
DROP TRIGGER IF EXISTS trg_users_atualizado_em ON users;
CREATE TRIGGER trg_users_atualizado_em
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION fn_set_atualizado_em();

-- monitoramentos
DROP TRIGGER IF EXISTS trg_monitoramentos_atualizado_em ON monitoramentos;
CREATE TRIGGER trg_monitoramentos_atualizado_em
    BEFORE UPDATE ON monitoramentos
    FOR EACH ROW EXECUTE FUNCTION fn_set_atualizado_em();

-- oportunidades
DROP TRIGGER IF EXISTS trg_oportunidades_atualizado_em ON oportunidades;
CREATE TRIGGER trg_oportunidades_atualizado_em
    BEFORE UPDATE ON oportunidades
    FOR EACH ROW EXECUTE FUNCTION fn_set_atualizado_em();

-- documentos
DROP TRIGGER IF EXISTS trg_documentos_atualizado_em ON documentos;
CREATE TRIGGER trg_documentos_atualizado_em
    BEFORE UPDATE ON documentos
    FOR EACH ROW EXECUTE FUNCTION fn_set_atualizado_em();

-- equipe_membros
DROP TRIGGER IF EXISTS trg_equipe_membros_atualizado_em ON equipe_membros;
CREATE TRIGGER trg_equipe_membros_atualizado_em
    BEFORE UPDATE ON equipe_membros
    FOR EACH ROW EXECUTE FUNCTION fn_set_atualizado_em();

-- certidoes
DROP TRIGGER IF EXISTS trg_certidoes_atualizado_em ON certidoes;
CREATE TRIGGER trg_certidoes_atualizado_em
    BEFORE UPDATE ON certidoes
    FOR EACH ROW EXECUTE FUNCTION fn_set_atualizado_em();

-- ---------------------------------------------------------------------------
-- Triggers de contagem de alertas em monitoramentos
-- ---------------------------------------------------------------------------

DROP TRIGGER IF EXISTS trg_alertas_incrementar ON alertas;
CREATE TRIGGER trg_alertas_incrementar
    AFTER INSERT ON alertas
    FOR EACH ROW EXECUTE FUNCTION fn_incrementar_total_alertas();

DROP TRIGGER IF EXISTS trg_alertas_decrementar ON alertas;
CREATE TRIGGER trg_alertas_decrementar
    AFTER DELETE ON alertas
    FOR EACH ROW EXECUTE FUNCTION fn_decrementar_total_alertas();

-- =============================================================================
-- VIEWS
-- =============================================================================

-- ---------------------------------------------------------------------------
-- v_certidoes_status
--   Certidões enriquecidas com status calculado e dias restantes.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_certidoes_status AS
SELECT
    c.id,
    c.user_id,
    c.nome,
    c.tipo,
    c.orgao_emissor,
    c.numero,
    c.data_emissao,
    c.data_vencimento,
    c.descricao,
    c.criado_em,
    c.atualizado_em,
    fn_status_certidao(c.data_vencimento)        AS status,
    fn_dias_para_vencer(c.data_vencimento)       AS dias_para_vencer
FROM certidoes c;

COMMENT ON VIEW v_certidoes_status IS
    'Certidões com status calculado (ativa/a_vencer/vencida/sem_prazo) e dias restantes para o vencimento.';

-- ---------------------------------------------------------------------------
-- v_certidoes_expirando
--   Apenas certidões que vencem nos próximos 30 dias ou já vencidas,
--   ordenadas por urgência. Usada nos widgets de compliance.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_certidoes_expirando AS
SELECT
    cs.*,
    u.nome          AS user_nome,
    u.email         AS user_email,
    u.empresa       AS user_empresa
FROM v_certidoes_status cs
JOIN users u ON u.id = cs.user_id
WHERE cs.data_vencimento IS NOT NULL
  AND cs.data_vencimento <= CURRENT_DATE + INTERVAL '30 days'
ORDER BY cs.data_vencimento ASC;

COMMENT ON VIEW v_certidoes_expirando IS
    'Certidões vencidas ou que vencem nos próximos 30 dias, com dados do usuário.';

-- ---------------------------------------------------------------------------
-- v_alertas_resumo
--   Contagem de alertas não lidos e última data de alerta por usuário,
--   para badges e indicadores de notificação.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_alertas_resumo AS
SELECT
    user_id,
    COUNT(*)                                        AS total_alertas,
    COUNT(*) FILTER (WHERE NOT lido)                AS nao_lidos,
    MAX(criado_em)                                  AS ultimo_alerta_em,
    COUNT(*) FILTER (
        WHERE NOT lido AND tipo = 'prazo_vencendo'
    )                                               AS nao_lidos_prazo
FROM alertas
GROUP BY user_id;

COMMENT ON VIEW v_alertas_resumo IS
    'Contagem de alertas por usuário, total e não lidos, útil para badges na interface.';

-- ---------------------------------------------------------------------------
-- v_oportunidades_pipeline
--   Pipeline comercial enriquecido: valor como NUMERIC, valor ponderado
--   pela probabilidade, prazo convertido para DATE, e urgência calculada.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_oportunidades_pipeline AS
SELECT
    o.id,
    o.user_id,
    o.titulo,
    o.estagio,
    o.valor_estimado,
    -- Tenta converter valor_estimado para numeric (NULL se não for numérico)
    CASE
        WHEN o.valor_estimado ~ '^[0-9]+(\.[0-9]+)?$'
        THEN o.valor_estimado::NUMERIC
        ELSE NULL
    END                                                     AS valor_numerico,
    -- Valor ponderado pela probabilidade
    CASE
        WHEN o.valor_estimado ~ '^[0-9]+(\.[0-9]+)?$'
             AND o.probabilidade IS NOT NULL
        THEN ROUND(o.valor_estimado::NUMERIC * o.probabilidade / 100.0, 2)
        ELSE NULL
    END                                                     AS valor_ponderado,
    o.probabilidade,
    o.licitacao_id,
    o.licitacao_objeto,
    o.responsavel_nome,
    o.responsavel_id,
    o.prazo,
    -- Prazo como DATE para comparações
    CASE
        WHEN o.prazo ~ '^\d{4}-\d{2}-\d{2}'
        THEN o.prazo::DATE
        ELSE NULL
    END                                                     AS prazo_date,
    -- Dias até o prazo (negativo = vencido)
    CASE
        WHEN o.prazo ~ '^\d{4}-\d{2}-\d{2}'
        THEN (o.prazo::DATE - CURRENT_DATE)::INTEGER
        ELSE NULL
    END                                                     AS dias_para_prazo,
    -- Urgência do prazo
    CASE
        WHEN o.prazo IS NULL OR NOT (o.prazo ~ '^\d{4}-\d{2}-\d{2}')
            THEN 'sem_prazo'
        WHEN o.prazo::DATE < CURRENT_DATE
            THEN 'vencido'
        WHEN o.prazo::DATE <= CURRENT_DATE + INTERVAL '7 days'
            THEN 'critico'
        WHEN o.prazo::DATE <= CURRENT_DATE + INTERVAL '30 days'
            THEN 'atencao'
        ELSE 'normal'
    END                                                     AS urgencia,
    o.notas,
    o.tags,
    o.criado_em,
    o.atualizado_em
FROM oportunidades o;

COMMENT ON VIEW v_oportunidades_pipeline IS
    'Pipeline comercial com valor numérico, valor ponderado por probabilidade, prazo como DATE e urgência calculada.';

-- ---------------------------------------------------------------------------
-- v_agenda
--   Visão unificada de todos os eventos com prazo:
--     - Oportunidades com prazo definido (estagio ativo)
--     - Certidões a vencer ou vencidas
--     - Alertas de prazo não lidos
--   Útil para a página de Agenda e notificações.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_agenda AS

-- Oportunidades com prazo
SELECT
    'oportunidade'::TEXT                                    AS tipo,
    o.id::TEXT                                              AS origem_id,
    o.user_id,
    o.titulo,
    o.prazo::DATE                                           AS data_evento,
    CASE
        WHEN o.prazo::DATE < CURRENT_DATE                   THEN 'vencido'
        WHEN o.prazo::DATE <= CURRENT_DATE + INTERVAL '7 days'  THEN 'critico'
        WHEN o.prazo::DATE <= CURRENT_DATE + INTERVAL '30 days' THEN 'atencao'
        ELSE 'normal'
    END                                                     AS urgencia,
    '/oportunidades'                                        AS link,
    o.estagio                                               AS detalhe
FROM oportunidades o
WHERE o.prazo ~ '^\d{4}-\d{2}-\d{2}'
  AND o.estagio NOT IN ('ganhou', 'perdeu')
  AND o.prazo::DATE >= CURRENT_DATE - INTERVAL '7 days'
  AND o.prazo::DATE <= CURRENT_DATE + INTERVAL '60 days'

UNION ALL

-- Certidões vencidas ou a vencer (próximos 60 dias)
SELECT
    'certidao'::TEXT                                        AS tipo,
    c.id::TEXT                                              AS origem_id,
    c.user_id,
    c.nome                                                  AS titulo,
    c.data_vencimento                                       AS data_evento,
    fn_status_certidao(c.data_vencimento)                   AS urgencia,
    '/certidoes'                                            AS link,
    c.tipo                                                  AS detalhe
FROM certidoes c
WHERE c.data_vencimento IS NOT NULL
  AND c.data_vencimento >= CURRENT_DATE - INTERVAL '7 days'
  AND c.data_vencimento <= CURRENT_DATE + INTERVAL '60 days'

UNION ALL

-- Alertas de prazo_vencendo não lidos
SELECT
    'alerta'::TEXT                                          AS tipo,
    a.id::TEXT                                              AS origem_id,
    a.user_id,
    a.titulo,
    a.criado_em::DATE                                       AS data_evento,
    CASE
        WHEN a.criado_em < NOW() - INTERVAL '3 days' THEN 'critico'
        ELSE 'atencao'
    END                                                     AS urgencia,
    COALESCE('/licitacoes/' || a.licitacao_id, '/alertas') AS link,
    a.tipo                                                  AS detalhe
FROM alertas a
WHERE a.tipo = 'prazo_vencendo'
  AND NOT a.lido
  AND a.criado_em >= NOW() - INTERVAL '7 days'

ORDER BY data_evento ASC, urgencia ASC;

COMMENT ON VIEW v_agenda IS
    'Agenda unificada: oportunidades com prazo, certidões a vencer e alertas de prazo não lidos, nos próximos 60 dias.';

-- ---------------------------------------------------------------------------
-- v_dashboard_kpis
--   KPIs agregados por usuário para o widget do Dashboard.
--   Calculados em tempo real; para volumes maiores, materializar com REFRESH.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_dashboard_kpis AS
SELECT
    u.id                                                        AS user_id,
    u.nome,
    u.email,
    u.plano,

    -- Favoritos
    (SELECT COUNT(*) FROM favoritos f WHERE f.user_id = u.id)   AS total_favoritos,

    -- Monitoramentos ativos
    (SELECT COUNT(*) FROM monitoramentos m
     WHERE m.user_id = u.id AND m.ativo)                        AS monitoramentos_ativos,

    -- Alertas não lidos
    (SELECT COUNT(*) FROM alertas a
     WHERE a.user_id = u.id AND NOT a.lido)                     AS alertas_nao_lidos,

    -- Oportunidades por estágio
    (SELECT COUNT(*) FROM oportunidades o
     WHERE o.user_id = u.id
       AND o.estagio NOT IN ('ganhou', 'perdeu'))               AS oportunidades_ativas,

    (SELECT COUNT(*) FROM oportunidades o
     WHERE o.user_id = u.id AND o.estagio = 'ganhou')          AS oportunidades_ganhas,

    (SELECT COUNT(*) FROM oportunidades o
     WHERE o.user_id = u.id AND o.estagio = 'perdeu')          AS oportunidades_perdidas,

    -- Valor total do pipeline ativo (somente valores numéricos)
    (SELECT COALESCE(SUM(
         CASE WHEN valor_estimado ~ '^[0-9]+(\.[0-9]+)?$'
              THEN valor_estimado::NUMERIC ELSE 0 END), 0)
     FROM oportunidades o
     WHERE o.user_id = u.id
       AND o.estagio NOT IN ('ganhou', 'perdeu'))               AS valor_pipeline_ativo,

    -- Valor total ganho
    (SELECT COALESCE(SUM(
         CASE WHEN valor_estimado ~ '^[0-9]+(\.[0-9]+)?$'
              THEN valor_estimado::NUMERIC ELSE 0 END), 0)
     FROM oportunidades o
     WHERE o.user_id = u.id AND o.estagio = 'ganhou')          AS valor_ganho,

    -- Taxa de vitória (ganhou / (ganhou + perdeu)) em %
    CASE
        WHEN (SELECT COUNT(*) FROM oportunidades o
              WHERE o.user_id = u.id
                AND o.estagio IN ('ganhou', 'perdeu')) = 0
        THEN NULL
        ELSE ROUND(
            100.0 * (SELECT COUNT(*) FROM oportunidades o
                     WHERE o.user_id = u.id AND o.estagio = 'ganhou')
            /
            (SELECT COUNT(*) FROM oportunidades o
             WHERE o.user_id = u.id AND o.estagio IN ('ganhou', 'perdeu'))
        , 1)
    END                                                         AS taxa_vitoria,

    -- Certidões a vencer nos próximos 30 dias (incluindo vencidas)
    (SELECT COUNT(*) FROM certidoes c
     WHERE c.user_id = u.id
       AND c.data_vencimento IS NOT NULL
       AND c.data_vencimento <= CURRENT_DATE + INTERVAL '30 days') AS certidoes_atencao,

    -- Membros de equipe ativos
    (SELECT COUNT(*) FROM equipe_membros em
     WHERE em.owner_id = u.id AND em.status = 'ativo')         AS equipe_ativos,

    -- Documentos cadastrados
    (SELECT COUNT(*) FROM documentos d
     WHERE d.user_id = u.id)                                    AS total_documentos

FROM users u;

COMMENT ON VIEW v_dashboard_kpis IS
    'KPIs agregados por usuário para o Dashboard: pipeline, alertas, certidões, taxa de vitória.';

-- ---------------------------------------------------------------------------
-- v_monitoramentos_stats
--   Monitoramentos com contagem real de alertas (reconcilia o contador
--   em caso de inserções manuais que contornem o trigger).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_monitoramentos_stats AS
SELECT
    m.*,
    COUNT(a.id)                                             AS alertas_count_real,
    COUNT(a.id) FILTER (WHERE NOT a.lido)                   AS alertas_nao_lidos,
    MAX(a.criado_em)                                        AS ultimo_alerta_em
FROM monitoramentos m
LEFT JOIN alertas a ON a.monitoramento_id = m.id
GROUP BY m.id;

COMMENT ON VIEW v_monitoramentos_stats IS
    'Monitoramentos com contagem real de alertas calculada via JOIN (reconcilia divergências do trigger).';

-- =============================================================================
-- GERENCIAMENTO DE LICITAÇÕES
-- =============================================================================

-- ---------------------------------------------------------------------------
-- licitacoes_gerenciadas — licitações que a empresa está participando
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS licitacoes_gerenciadas (
    id                        SERIAL PRIMARY KEY,
    user_id                   TEXT        NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    licitacao_id              TEXT        NOT NULL,
    licitacao_numero          TEXT,
    licitacao_objeto          TEXT,
    licitacao_orgao           TEXT,
    licitacao_cnpj            TEXT,
    licitacao_uf              TEXT,
    licitacao_municipio       TEXT,
    licitacao_modalidade      TEXT,
    licitacao_situacao        TEXT,
    licitacao_valor           NUMERIC(18,2),
    licitacao_data_abertura   DATE,
    licitacao_data_encerramento DATE,
    licitacao_data_publicacao DATE,
    licitacao_link_pncp       TEXT,
    status                    TEXT        NOT NULL DEFAULT 'em_andamento'
                                          CHECK (status IN ('em_andamento','finalizada','cancelada')),
    notas_gerais              TEXT,
    responsavel               TEXT,
    resultado                 TEXT        CHECK (resultado IN ('ganhou','perdeu','desistiu')),
    valor_proposta            NUMERIC(18,2),
    criado_em                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, licitacao_id)
);

CREATE INDEX IF NOT EXISTS idx_lic_ger_user_id    ON licitacoes_gerenciadas (user_id);
CREATE INDEX IF NOT EXISTS idx_lic_ger_status     ON licitacoes_gerenciadas (user_id, status);

CREATE TRIGGER trg_lic_ger_atualizado_em
    BEFORE UPDATE ON licitacoes_gerenciadas
    FOR EACH ROW EXECUTE FUNCTION fn_set_atualizado_em();

-- ---------------------------------------------------------------------------
-- gerenciamento_tarefas — tarefas vinculadas a uma licitação gerenciada
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gerenciamento_tarefas (
    id                SERIAL PRIMARY KEY,
    gerenciamento_id  INTEGER     NOT NULL REFERENCES licitacoes_gerenciadas(id) ON DELETE CASCADE,
    titulo            TEXT        NOT NULL,
    descricao         TEXT,
    prazo             DATE,
    concluida         BOOLEAN     NOT NULL DEFAULT FALSE,
    concluida_em      TIMESTAMPTZ,
    prioridade        TEXT        NOT NULL DEFAULT 'normal'
                                  CHECK (prioridade IN ('baixa','normal','alta','urgente')),
    categoria         TEXT        NOT NULL DEFAULT 'geral'
                                  CHECK (categoria IN ('geral','edital','proposta','habilitacao','recurso','contrato','disputa')),
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ger_tarefas_ger_id ON gerenciamento_tarefas (gerenciamento_id);
CREATE INDEX IF NOT EXISTS idx_ger_tarefas_prazo  ON gerenciamento_tarefas (prazo) WHERE NOT concluida;

CREATE TRIGGER trg_ger_tarefas_atualizado_em
    BEFORE UPDATE ON gerenciamento_tarefas
    FOR EACH ROW EXECUTE FUNCTION fn_set_atualizado_em();

-- ---------------------------------------------------------------------------
-- gerenciamento_anotacoes — notas livres vinculadas a uma licitação gerenciada
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gerenciamento_anotacoes (
    id                SERIAL PRIMARY KEY,
    gerenciamento_id  INTEGER     NOT NULL REFERENCES licitacoes_gerenciadas(id) ON DELETE CASCADE,
    conteudo          TEXT        NOT NULL,
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ger_anotacoes_ger_id ON gerenciamento_anotacoes (gerenciamento_id);

CREATE TRIGGER trg_ger_anotacoes_atualizado_em
    BEFORE UPDATE ON gerenciamento_anotacoes
    FOR EACH ROW EXECUTE FUNCTION fn_set_atualizado_em();

-- =============================================================================
-- FIM DO SCRIPT
-- =============================================================================
