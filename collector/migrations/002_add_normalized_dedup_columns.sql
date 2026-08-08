-- Migration 002: Add normalised columns for fuzzy cross-portal deduplication
--
-- Adds objeto_norm and orgao_norm (canonical lowercase, accent-stripped, whitespace-
-- collapsed forms of objeto/orgao) so that near-duplicate tenders from different
-- portals are caught even when minor text variations exist.
--
-- This migration is IDEMPOTENT — it can be re-run safely against a database that
-- already has the columns or index.
--
-- NOTE: schema.sql already contains the ALTER TABLE ADD COLUMN IF NOT EXISTS
-- statements so the Collector startup (apply_schema) handles existing databases
-- automatically.  This file is provided as a standalone script for operators who
-- want to upgrade an existing production database explicitly and also back-fill
-- the normalised values for pre-existing rows.
--
-- Run once:
--   psql $DATABASE_URL -f collector/migrations/002_add_normalized_dedup_columns.sql

-- ── 1. Add columns (idempotent) ───────────────────────────────────────────────
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS objeto_norm TEXT;
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS orgao_norm  TEXT;

-- ── 2. Create the normalised dedup index (idempotent) ─────────────────────────
CREATE INDEX IF NOT EXISTS idx_tenders_dedup_norm
    ON tenders (objeto_norm text_pattern_ops, orgao_norm text_pattern_ops, data_publicacao)
    WHERE objeto_norm IS NOT NULL AND orgao_norm IS NOT NULL AND data_publicacao IS NOT NULL;

-- ── 3. Back-fill normalised columns for existing rows ─────────────────────────
-- We attempt to use the unaccent extension for accent-stripping.
-- If the extension is unavailable or the role lacks permission to create it,
-- we fall back to lowercase + whitespace-collapsing only.
-- The Python processor (_normalize_for_dedup) will produce fully correct
-- normalised values on the next upsert; this back-fill is best-effort.

DO $$
DECLARE
    _has_unaccent BOOLEAN;
BEGIN
    -- Check whether unaccent is already installed (don't try to CREATE it here
    -- to avoid permission errors on managed databases).
    SELECT EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'unaccent'
    ) INTO _has_unaccent;

    IF _has_unaccent THEN
        -- Full back-fill: lowercase + strip accents + collapse whitespace
        UPDATE tenders
        SET
            objeto_norm = regexp_replace(
                              lower(unaccent(regexp_replace(trim(objeto), '\s+', ' ', 'g'))),
                              '\s+', ' ', 'g'),
            orgao_norm  = regexp_replace(
                              lower(unaccent(regexp_replace(trim(orgao),  '\s+', ' ', 'g'))),
                              '\s+', ' ', 'g')
        WHERE (objeto IS NOT NULL OR orgao IS NOT NULL)
          AND (objeto_norm IS NULL OR orgao_norm IS NULL);

        RAISE NOTICE 'Back-fill complete using unaccent (accent stripping enabled).';
    ELSE
        -- Partial back-fill: lowercase + collapse whitespace only (no accent stripping).
        -- The Python processor will produce fully correct values on next upsert.
        UPDATE tenders
        SET
            objeto_norm = regexp_replace(lower(regexp_replace(trim(objeto), '\s+', ' ', 'g')),
                                         '\s+', ' ', 'g'),
            orgao_norm  = regexp_replace(lower(regexp_replace(trim(orgao),  '\s+', ' ', 'g')),
                                         '\s+', ' ', 'g')
        WHERE (objeto IS NOT NULL OR orgao IS NOT NULL)
          AND (objeto_norm IS NULL OR orgao_norm IS NULL);

        RAISE NOTICE 'Back-fill complete WITHOUT unaccent (extension not installed). '
                     'Accent-stripping will be applied by the Python processor on next upsert.';
    END IF;
END
$$;
