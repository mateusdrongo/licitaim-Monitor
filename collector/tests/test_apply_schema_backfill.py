"""
Tests for the apply_schema back-fill path.

Verifies that when apply_schema encounters existing tenders with NULL
objeto_norm / orgao_norm columns, it correctly computes and stores the
normalised values using the same Python logic as TenderProcessor.

The pool/connection is fully mocked so no real database is required.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.app.processors.tender_processor import TenderProcessor


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_mock_pool(existing_rows: list) -> AsyncMock:
    """
    Return a mock asyncpg Pool that:
      - pool.execute(sql) → succeeds (DDL)
      - pool.fetch(sql) → returns `existing_rows` (rows needing back-fill)
      - pool.executemany(sql, updates) → records the update batches
      - pool.close() → no-op
    """
    pool = AsyncMock()
    pool.execute = AsyncMock(return_value=None)
    pool.fetch = AsyncMock(return_value=existing_rows)
    pool.executemany = AsyncMock(return_value=None)
    pool.close = AsyncMock(return_value=None)
    return pool


def _make_asyncpg_row(id_: str, objeto: str | None, orgao: str | None) -> MagicMock:
    """Minimal asyncpg Record-like mock."""
    data = {"id": id_, "objeto": objeto, "orgao": orgao}
    row = MagicMock()
    row.__getitem__ = lambda self, key: data[key]
    return row


def _create_pool_mock(pool: AsyncMock):
    """AsyncMock for asyncpg.create_pool that returns the given pool when awaited."""
    return AsyncMock(return_value=pool)


# ── tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_backfill_normalises_accent_variants(tmp_path):
    """
    apply_schema must write normalised (accent-stripped, lowercased) values
    for existing rows that have NULL objeto_norm / orgao_norm.
    """
    row_id = str(uuid.uuid4())
    existing = [
        _make_asyncpg_row(row_id, "Aquisição de Equipamentos", "Ministério da Educação")
    ]
    mock_pool = _make_mock_pool(existing)

    schema_file = tmp_path / "schema.sql"
    schema_file.write_text("-- no-op for test\n")

    with (
        patch("collector.app.standalone.asyncpg.create_pool",
              new=_create_pool_mock(mock_pool)),
        patch("collector.app.standalone.os.path.join", return_value=str(schema_file)),
    ):
        from collector.app.standalone import apply_schema
        await apply_schema("postgresql://test/test")

    # executemany must have been called with normalised values
    mock_pool.executemany.assert_awaited_once()
    _sql, updates = mock_pool.executemany.call_args.args

    assert len(updates) == 1
    obj_norm, org_norm, _id = updates[0]

    expected_obj = TenderProcessor._normalize_for_dedup("Aquisição de Equipamentos")
    expected_org = TenderProcessor._normalize_for_dedup("Ministério da Educação")

    assert obj_norm == expected_obj
    assert org_norm == expected_org
    assert obj_norm == "aquisicao de equipamentos"
    assert org_norm == "ministerio da educacao"
    assert _id == row_id


@pytest.mark.asyncio
async def test_backfill_normalises_caps_variant(tmp_path):
    """
    Rows whose objeto/orgao are in ALL CAPS must produce the same canonical
    form as mixed-case equivalents.
    """
    row_id = str(uuid.uuid4())
    existing = [
        _make_asyncpg_row(row_id, "AQUISIÇÃO DE EQUIPAMENTOS", "MINISTÉRIO DA EDUCAÇÃO")
    ]
    mock_pool = _make_mock_pool(existing)

    schema_file = tmp_path / "schema.sql"
    schema_file.write_text("-- no-op for test\n")

    with (
        patch("collector.app.standalone.asyncpg.create_pool",
              new=_create_pool_mock(mock_pool)),
        patch("collector.app.standalone.os.path.join", return_value=str(schema_file)),
    ):
        from collector.app.standalone import apply_schema
        await apply_schema("postgresql://test/test")

    _sql, updates = mock_pool.executemany.call_args.args
    obj_norm, org_norm, _ = updates[0]

    assert obj_norm == "aquisicao de equipamentos"
    assert org_norm == "ministerio da educacao"


@pytest.mark.asyncio
async def test_backfill_skipped_when_no_null_rows(tmp_path):
    """
    If all existing rows already have objeto_norm / orgao_norm populated,
    apply_schema must NOT call executemany (no back-fill needed).
    """
    mock_pool = _make_mock_pool([])  # empty → no rows need back-fill

    schema_file = tmp_path / "schema.sql"
    schema_file.write_text("-- no-op for test\n")

    with (
        patch("collector.app.standalone.asyncpg.create_pool",
              new=_create_pool_mock(mock_pool)),
        patch("collector.app.standalone.os.path.join", return_value=str(schema_file)),
    ):
        from collector.app.standalone import apply_schema
        await apply_schema("postgresql://test/test")

    mock_pool.executemany.assert_not_awaited()


@pytest.mark.asyncio
async def test_backfill_handles_none_objeto(tmp_path):
    """
    Rows where objeto is None must not crash the back-fill;
    the normalised value for None must be None.
    """
    row_id = str(uuid.uuid4())
    existing = [_make_asyncpg_row(row_id, None, "Ministério da Educação")]
    mock_pool = _make_mock_pool(existing)

    schema_file = tmp_path / "schema.sql"
    schema_file.write_text("-- no-op for test\n")

    with (
        patch("collector.app.standalone.asyncpg.create_pool",
              new=_create_pool_mock(mock_pool)),
        patch("collector.app.standalone.os.path.join", return_value=str(schema_file)),
    ):
        from collector.app.standalone import apply_schema
        await apply_schema("postgresql://test/test")

    _sql, updates = mock_pool.executemany.call_args.args
    obj_norm, org_norm, _ = updates[0]

    assert obj_norm is None
    assert org_norm == "ministerio da educacao"
