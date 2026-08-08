"""
Tests for TenderProcessor — verifies cross-portal deduplication logic,
including fuzzy near-duplicate detection via normalised columns.

The pool/connection is fully mocked so no real database is required.
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.app.processors.tender_processor import TenderProcessor


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_pool(conn_mock: AsyncMock) -> MagicMock:
    """Return a mock asyncpg Pool whose acquire() context-manager yields conn_mock."""
    pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield conn_mock

    pool.acquire = _acquire
    return pool


def _base_tender(**overrides) -> dict:
    base = dict(
        source="pncp",
        external_id="PNCP-001",
        objeto="Aquisição de computadores",
        orgao="Ministério da Educação",
        data_publicacao="2024-03-15",
        modalidade="Pregão Eletrônico",
        situacao="Aberta",
        uf="DF",
        municipio="Brasília",
    )
    base.update(overrides)
    return base


# ── cross-portal dedup ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cross_portal_duplicate_returns_existing_id(caplog):
    """
    When a tender from a different source has the same objeto/orgao/data_publicacao,
    _upsert_tender must return the id of the already-inserted row WITHOUT
    inserting a new one.
    """
    existing_id = str(uuid.uuid4())

    conn = AsyncMock()

    # First call to fetchrow (source+external_id lookup): not found → None
    # Second call to fetchrow (cross-portal dedup query): found → existing row
    cross_dup_record = MagicMock()
    cross_dup_record.__getitem__ = lambda self, key: (
        existing_id if key == "id" else "pncp"
    )
    cross_dup_record.get = lambda key, default=None: (
        existing_id if key == "id" else "pncp"
    )

    conn.fetchrow.side_effect = [None, cross_dup_record]

    pool = _make_pool(conn)

    processor = TenderProcessor(pool)

    # Suppress ES publish (fire-and-forget, irrelevant here)
    with patch.object(processor, "_publish_es_event", new=AsyncMock()):
        with caplog.at_level(logging.WARNING, logger="collector.processor"):
            result = await processor.process(
                _base_tender(
                    source="comprasnet",
                    external_id="CN-999",
                )
            )

    assert result == existing_id, (
        f"Expected existing tender id {existing_id!r}, got {result!r}"
    )


@pytest.mark.asyncio
async def test_cross_portal_duplicate_emits_warning(caplog):
    """
    A warning log must be emitted when a cross-portal duplicate is detected.
    """
    existing_id = str(uuid.uuid4())

    conn = AsyncMock()

    cross_dup_record = MagicMock()
    cross_dup_record.__getitem__ = lambda self, key: (
        existing_id if key == "id" else "pncp"
    )
    cross_dup_record.get = lambda key, default=None: (
        existing_id if key == "id" else "pncp"
    )

    conn.fetchrow.side_effect = [None, cross_dup_record]

    pool = _make_pool(conn)
    processor = TenderProcessor(pool)

    with patch.object(processor, "_publish_es_event", new=AsyncMock()):
        with caplog.at_level(logging.WARNING, logger="collector.processor"):
            await processor.process(
                _base_tender(source="comprasnet", external_id="CN-999")
            )

    warning_records = [
        r for r in caplog.records
        if r.levelno == logging.WARNING and "duplicado ignorado" in r.message
    ]
    assert warning_records, (
        "Expected a WARNING log containing 'duplicado ignorado' but none was emitted. "
        f"Captured records: {[r.message for r in caplog.records]}"
    )


@pytest.mark.asyncio
async def test_cross_portal_duplicate_does_not_insert(caplog):
    """
    When a cross-portal duplicate is detected, no INSERT should be executed.
    """
    existing_id = str(uuid.uuid4())

    conn = AsyncMock()

    cross_dup_record = MagicMock()
    cross_dup_record.__getitem__ = lambda self, key: (
        existing_id if key == "id" else "pncp"
    )
    cross_dup_record.get = lambda key, default=None: (
        existing_id if key == "id" else "pncp"
    )

    conn.fetchrow.side_effect = [None, cross_dup_record]

    pool = _make_pool(conn)
    processor = TenderProcessor(pool)

    with patch.object(processor, "_publish_es_event", new=AsyncMock()):
        await processor.process(
            _base_tender(source="comprasnet", external_id="CN-999")
        )

    # conn.execute is used for UPDATE and INSERT; neither should be called
    # when a cross-portal dup is detected.
    for call in conn.execute.call_args_list:
        sql = call.args[0] if call.args else ""
        assert "INSERT INTO tenders" not in sql.upper(), (
            "INSERT INTO tenders was called despite a cross-portal duplicate existing"
        )


@pytest.mark.asyncio
async def test_no_dedup_when_fields_missing():
    """
    When objeto, orgao, or data_publicacao is absent, the cross-portal dedup
    query must NOT be issued and the tender should be inserted normally.
    """
    new_id = str(uuid.uuid4())

    conn = AsyncMock()

    inserted_row = MagicMock()
    inserted_row.__getitem__ = lambda self, key: new_id if key == "id" else None

    # First fetchrow (source+external_id lookup): not found
    # No second fetchrow should be called because objeto is missing
    conn.fetchrow.side_effect = [None]
    conn.fetchrow.return_value = None

    # The INSERT returns the new row
    async def _fetchrow_side_effect(*args, **kwargs):
        sql = args[0] if args else ""
        if "INSERT INTO tenders" in sql:
            return inserted_row
        return None

    conn.fetchrow.side_effect = _fetchrow_side_effect

    pool = _make_pool(conn)
    processor = TenderProcessor(pool)

    with patch.object(processor, "_publish_es_event", new=AsyncMock()):
        result = await processor.process(
            _base_tender(
                source="comprasnet",
                external_id="CN-NOOBJETO",
                objeto=None,  # missing → dedup query skipped
            )
        )

    # Should have attempted to insert (fetchrow called once for INSERT path,
    # never for cross-portal dedup)
    insert_calls = [
        call for call in conn.fetchrow.call_args_list
        if call.args and "SELECT id, source FROM tenders" in call.args[0]
    ]
    assert not insert_calls, (
        "Cross-portal dedup query should NOT be issued when objeto is None"
    )


# ── _normalize_for_dedup unit tests ───────────────────────────────────────────

class TestNormalizeForDedup:
    """Unit tests for the canonical normalisation helper."""

    def test_lowercases(self):
        result = TenderProcessor._normalize_for_dedup("MINISTÉRIO DA EDUCAÇÃO")
        assert result == result.lower()

    def test_strips_accents(self):
        result = TenderProcessor._normalize_for_dedup("Aquisição de Equipamentos")
        assert "ç" not in result
        assert "ã" not in result
        assert "aquisicao de equipamentos" == result

    def test_collapses_whitespace(self):
        result = TenderProcessor._normalize_for_dedup("  Ministério   da   Educação  ")
        assert "  " not in result
        assert result == result.strip()

    def test_none_returns_none(self):
        assert TenderProcessor._normalize_for_dedup(None) is None

    def test_empty_string_returns_none(self):
        assert TenderProcessor._normalize_for_dedup("   ") is None

    def test_variant_accents_same_canonical(self):
        """Different accent representations collapse to the same canonical form."""
        a = TenderProcessor._normalize_for_dedup("Ministério da Educação")
        b = TenderProcessor._normalize_for_dedup("MINISTERIO DA EDUCACAO")
        assert a == b

    def test_extra_spaces_same_canonical(self):
        a = TenderProcessor._normalize_for_dedup("Pregão  Eletrônico")
        b = TenderProcessor._normalize_for_dedup("Pregão Eletrônico")
        assert a == b


# ── near-duplicate cross-portal dedup ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_near_duplicate_accent_variant_detected(caplog):
    """
    A tender from a second portal whose objeto/orgao differ only in accents
    should be caught by the normalised dedup query and not inserted.
    """
    existing_id = str(uuid.uuid4())
    conn = AsyncMock()

    cross_dup_record = MagicMock()
    cross_dup_record.__getitem__ = lambda self, key: (
        existing_id if key == "id" else "pncp"
    )

    # First fetchrow (source+external_id): not found
    # Second fetchrow (normalised cross-portal dedup): found
    conn.fetchrow.side_effect = [None, cross_dup_record]

    pool = _make_pool(conn)
    processor = TenderProcessor(pool)

    with patch.object(processor, "_publish_es_event", new=AsyncMock()):
        with caplog.at_level(logging.WARNING, logger="collector.processor"):
            result = await processor.process(
                _base_tender(
                    source="comprasnet",
                    external_id="CN-ACCENT",
                    # Same tender as the base but without accents — portals differ
                    objeto="Aquisicao de computadores",
                    orgao="Ministerio da Educacao",
                )
            )

    assert result == existing_id
    assert any("duplicado ignorado" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_near_duplicate_casing_variant_detected(caplog):
    """
    A tender whose objeto/orgao are in ALL CAPS should still be deduplicated
    against a mixed-case existing row.
    """
    existing_id = str(uuid.uuid4())
    conn = AsyncMock()

    cross_dup_record = MagicMock()
    cross_dup_record.__getitem__ = lambda self, key: (
        existing_id if key == "id" else "pncp"
    )

    conn.fetchrow.side_effect = [None, cross_dup_record]

    pool = _make_pool(conn)
    processor = TenderProcessor(pool)

    with patch.object(processor, "_publish_es_event", new=AsyncMock()):
        with caplog.at_level(logging.WARNING, logger="collector.processor"):
            result = await processor.process(
                _base_tender(
                    source="bbmnet",
                    external_id="BBM-CAPS",
                    objeto="AQUISIÇÃO DE COMPUTADORES",
                    orgao="MINISTÉRIO DA EDUCAÇÃO",
                )
            )

    assert result == existing_id
    assert any("duplicado ignorado" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_near_duplicate_extra_spaces_detected(caplog):
    """
    Extra internal spaces in objeto/orgao must not prevent dedup from matching.
    """
    existing_id = str(uuid.uuid4())
    conn = AsyncMock()

    cross_dup_record = MagicMock()
    cross_dup_record.__getitem__ = lambda self, key: (
        existing_id if key == "id" else "pncp"
    )

    conn.fetchrow.side_effect = [None, cross_dup_record]

    pool = _make_pool(conn)
    processor = TenderProcessor(pool)

    with patch.object(processor, "_publish_es_event", new=AsyncMock()):
        with caplog.at_level(logging.WARNING, logger="collector.processor"):
            result = await processor.process(
                _base_tender(
                    source="bec_sp",
                    external_id="BEC-SPACES",
                    objeto="Aquisição  de  computadores",   # extra spaces
                    orgao="Ministério  da  Educação",       # extra spaces
                )
            )

    assert result == existing_id
    assert any("duplicado ignorado" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_dedup_uses_normalized_columns_in_query():
    """
    The cross-portal dedup query must use objeto_norm / orgao_norm columns,
    not the raw objeto / orgao values.
    """
    conn = AsyncMock()

    # No duplicate found — we just want to inspect what query was issued
    new_row = MagicMock()
    new_row.__getitem__ = lambda self, key: str(uuid.uuid4()) if key == "id" else None

    async def _fetchrow_side(*args, **kwargs):
        sql = args[0] if args else ""
        if "INSERT INTO tenders" in sql:
            return new_row
        return None

    conn.fetchrow.side_effect = _fetchrow_side

    pool = _make_pool(conn)
    processor = TenderProcessor(pool)

    with patch.object(processor, "_publish_es_event", new=AsyncMock()):
        await processor.process(_base_tender(source="comprasnet", external_id="CN-NORM-CHECK"))

    # Inspect all fetchrow calls; the dedup query must reference objeto_norm / orgao_norm
    dedup_calls = [
        call for call in conn.fetchrow.call_args_list
        if call.args and "objeto_norm" in call.args[0]
    ]
    assert dedup_calls, (
        "Expected a fetchrow call referencing 'objeto_norm' for cross-portal dedup, "
        f"but got: {[c.args[0][:80] for c in conn.fetchrow.call_args_list]}"
    )
