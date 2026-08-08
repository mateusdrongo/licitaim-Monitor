"""
Smoke test: back-fill then dedup.

Scenario:
  1. A tender row was inserted before the normalised-column migration, so its
     objeto_norm / orgao_norm are NULL.
  2. The collector restarts → apply_schema() back-fills those columns using the
     Python TenderProcessor._normalize_for_dedup logic.
  3. On the next scheduled run, the same tender arrives from a *second* portal
     with minor text variations (different accents / casing / extra spaces).
  4. TenderProcessor must detect the near-duplicate via the normalised columns
     and NOT insert a new row.

The key property being tested is that the values the processor sends to the
cross-portal dedup SELECT exactly match the values written by apply_schema's
back-fill.  The phase-2 mock only returns a duplicate when the query arguments
equal those exact normalized values; any regression that queries with wrong
(e.g. un-normalized, raw) values causes the mock to return None, which triggers
an INSERT — caught by the post-run assertion.

All database calls are mocked so no real PostgreSQL instance is needed.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.app.processors.tender_processor import TenderProcessor


# ── helpers ───────────────────────────────────────────────────────────────────

def _asyncpg_row(data: dict) -> MagicMock:
    """Minimal asyncpg Record-like mock."""
    row = MagicMock()
    row.__getitem__ = lambda self, key: data[key]
    row.get = lambda key, default=None: data.get(key, default)
    return row


def _make_apply_schema_pool(pre_migration_row: MagicMock) -> AsyncMock:
    """
    Pool for apply_schema():
      pool.execute(sql)          → succeeds (DDL / schema)
      pool.fetch(sql)            → returns [pre_migration_row] (rows needing back-fill)
      pool.executemany(sql, ...) → records what was written
      pool.close()               → no-op
    """
    pool = AsyncMock()
    pool.execute = AsyncMock(return_value=None)
    pool.fetch = AsyncMock(return_value=[pre_migration_row])
    pool.executemany = AsyncMock(return_value=None)
    pool.close = AsyncMock(return_value=None)
    return pool


def _make_processor_pool(conn_mock: AsyncMock) -> MagicMock:
    """Pool for TenderProcessor whose acquire() yields conn_mock."""
    pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield conn_mock

    pool.acquire = _acquire
    return pool


def _make_smart_conn(
    expected_obj_norm: str | None,
    expected_org_norm: str | None,
    existing_id: str,
    existing_source: str = "pncp",
) -> AsyncMock:
    """
    Return a mock connection whose fetchrow behaviour mirrors a real DB that has
    been back-filled:
      - Exact-key lookup (source + external_id): not found → None
      - Cross-portal dedup SELECT: returns existing row ONLY when the query
        arguments exactly match the expected normalised values.  If wrong values
        are passed the mock returns None, causing the processor to attempt an
        INSERT, which the test will then catch.
      - INSERT INTO tenders: returns a fresh row (should never be reached in the
        happy-path test, but must not crash if reached so the assertion can fire).
    """
    cross_dup_record = _asyncpg_row({"id": existing_id, "source": existing_source})
    fresh_id = str(uuid.uuid4())
    inserted_row = _asyncpg_row({"id": fresh_id})

    conn = AsyncMock()

    async def _fetchrow(*args, **kwargs):
        sql = args[0] if args else ""

        if "INSERT INTO tenders" in sql:
            return inserted_row  # should not be reached in the dup path

        # Cross-portal dedup query: only return the dup when the normalised args
        # are correct.  args[1]=obj_norm, args[2]=org_norm, args[3]=data_pub, args[4]=source
        if "source <>" in sql and "objeto_norm" in sql:
            queried_obj_norm = args[1] if len(args) > 1 else None
            queried_org_norm = args[2] if len(args) > 2 else None
            if queried_obj_norm == expected_obj_norm and queried_org_norm == expected_org_norm:
                return cross_dup_record
            return None  # wrong args → dup missed → INSERT will be caught below

        # Exact-key lookup: tender not found by (source, external_id)
        return None

    conn.fetchrow.side_effect = _fetchrow
    return conn


# ── tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_backfill_enables_near_duplicate_detection(tmp_path):
    """
    Full pipeline:
      Phase 1 — apply_schema back-fills objeto_norm / orgao_norm for a pre-migration row.
      Phase 2 — TenderProcessor.process() catches a near-duplicate from a second portal
                 that arrives with a minor accent/casing variant.

    The phase-2 mock only returns a duplicate when the dedup query arguments
    equal the normalised values that phase 1 wrote; wrong args → INSERT → assertion fails.
    """
    existing_id = str(uuid.uuid4())
    raw_objeto = "Aquisição de Equipamentos de TI"
    raw_orgao  = "Ministério da Educação"

    # ── Phase 1: apply_schema back-fills the NULL norm columns ───────────────
    pre_migration_row = _asyncpg_row({"id": existing_id, "objeto": raw_objeto, "orgao": raw_orgao})
    apply_schema_pool = _make_apply_schema_pool(pre_migration_row)

    schema_file = tmp_path / "schema.sql"
    schema_file.write_text("-- no-op\n")

    with (
        patch("collector.app.standalone.asyncpg.create_pool",
              new=AsyncMock(return_value=apply_schema_pool)),
        patch("collector.app.standalone.os.path.join",
              return_value=str(schema_file)),
    ):
        from collector.app.standalone import apply_schema
        await apply_schema("postgresql://test/test")

    apply_schema_pool.executemany.assert_awaited_once()
    _sql, updates = apply_schema_pool.executemany.call_args.args
    assert len(updates) == 1
    obj_norm_written, org_norm_written, updated_id = updates[0]

    expected_obj_norm = TenderProcessor._normalize_for_dedup(raw_objeto)
    expected_org_norm = TenderProcessor._normalize_for_dedup(raw_orgao)

    assert obj_norm_written == expected_obj_norm, (
        f"objeto_norm back-filled incorrectly: {obj_norm_written!r} != {expected_obj_norm!r}"
    )
    assert org_norm_written == expected_org_norm, (
        f"orgao_norm back-filled incorrectly: {org_norm_written!r} != {expected_org_norm!r}"
    )
    assert obj_norm_written == "aquisicao de equipamentos de ti"
    assert org_norm_written == "ministerio da educacao"
    assert updated_id == existing_id

    # ── Phase 2: next portal run → near-duplicate must be detected ───────────
    # The smart conn only returns the dup when the dedup query is called with the
    # exact values back-fill produced.  Wrong normalisation → None → INSERT → caught.
    conn = _make_smart_conn(obj_norm_written, org_norm_written, existing_id)
    processor = TenderProcessor(_make_processor_pool(conn))

    with patch.object(processor, "_publish_es_event", new=AsyncMock()):
        result = await processor.process({
            "source":          "comprasnet",
            "external_id":     "CN-BACKFILL-001",
            # Same tender, different portal — all-caps, no accents
            "objeto":          "AQUISICAO DE EQUIPAMENTOS DE TI",
            "orgao":           "MINISTERIO DA EDUCACAO",
            "data_publicacao": "2024-05-20",
            "modalidade":      "Pregão Eletrônico",
            "situacao":        "Aberta",
        })

    assert result == existing_id, (
        f"Expected existing id {existing_id!r} but got {result!r}. "
        "Near-duplicate from second portal was NOT caught after back-fill, "
        "or the dedup query was called with incorrect (non-normalised) values."
    )

    # Confirm the processor never attempted an INSERT
    for c in conn.execute.call_args_list:
        sql = (c.args[0] if c.args else "").lower()
        assert "insert into tenders" not in sql, (
            "INSERT INTO tenders was executed — near-duplicate slipped through the dedup check"
        )

    # Confirm the dedup SELECT referencing objeto_norm was actually issued
    dedup_calls = [
        c for c in conn.fetchrow.call_args_list
        if c.args and "objeto_norm" in c.args[0] and "source <>" in c.args[0]
    ]
    assert dedup_calls, "Cross-portal dedup SELECT was never issued."


@pytest.mark.asyncio
async def test_backfill_with_caps_variant_then_dedup(tmp_path):
    """
    Pre-migration row is ALL-CAPS; incoming near-duplicate has mixed case with
    accents.  Both must normalise to the same canonical form after back-fill.
    """
    existing_id = str(uuid.uuid4())
    raw_objeto = "CONTRATAÇÃO DE SERVIÇOS DE LIMPEZA"
    raw_orgao  = "PREFEITURA MUNICIPAL DE SÃO PAULO"

    pre_migration_row = _asyncpg_row({"id": existing_id, "objeto": raw_objeto, "orgao": raw_orgao})
    apply_schema_pool = _make_apply_schema_pool(pre_migration_row)

    schema_file = tmp_path / "schema.sql"
    schema_file.write_text("-- no-op\n")

    with (
        patch("collector.app.standalone.asyncpg.create_pool",
              new=AsyncMock(return_value=apply_schema_pool)),
        patch("collector.app.standalone.os.path.join",
              return_value=str(schema_file)),
    ):
        from collector.app.standalone import apply_schema
        await apply_schema("postgresql://test/test")

    _sql, updates = apply_schema_pool.executemany.call_args.args
    obj_norm_written, org_norm_written, _ = updates[0]

    assert obj_norm_written == "contratacao de servicos de limpeza"
    assert org_norm_written == "prefeitura municipal de sao paulo"

    # Phase 2: incoming tender uses mixed-case + accents — same canonical form
    conn = _make_smart_conn(obj_norm_written, org_norm_written, existing_id, "bec_sp")
    processor = TenderProcessor(_make_processor_pool(conn))

    with patch.object(processor, "_publish_es_event", new=AsyncMock()):
        result = await processor.process({
            "source":          "pncp",
            "external_id":     "PNCP-BACKFILL-002",
            "objeto":          "Contratação de Serviços de Limpeza",
            "orgao":           "Prefeitura Municipal de São Paulo",
            "data_publicacao": "2024-06-10",
        })

    assert result == existing_id, (
        "ALL-CAPS pre-migration row was not matched against a mixed-case near-duplicate "
        "after back-fill."
    )

    for c in conn.execute.call_args_list:
        sql = (c.args[0] if c.args else "").lower()
        assert "insert into tenders" not in sql, (
            "INSERT INTO tenders executed — casing-variant near-duplicate slipped through"
        )


@pytest.mark.asyncio
async def test_backfill_null_objeto_row_skips_dedup_query(tmp_path):
    """
    A pre-migration row whose objeto is NULL must not crash apply_schema.
    objeto_norm is back-filled as NULL; orgao_norm is computed normally.
    When the same tender arrives from a second portal (also with objeto=None),
    the cross-portal dedup query must NOT be issued (requires all three key
    fields to be non-NULL).
    """
    existing_id = str(uuid.uuid4())

    pre_migration_row = _asyncpg_row({
        "id":    existing_id,
        "objeto": None,
        "orgao":  "Câmara Municipal de Campinas",
    })
    apply_schema_pool = _make_apply_schema_pool(pre_migration_row)

    schema_file = tmp_path / "schema.sql"
    schema_file.write_text("-- no-op\n")

    with (
        patch("collector.app.standalone.asyncpg.create_pool",
              new=AsyncMock(return_value=apply_schema_pool)),
        patch("collector.app.standalone.os.path.join",
              return_value=str(schema_file)),
    ):
        from collector.app.standalone import apply_schema
        await apply_schema("postgresql://test/test")   # must not raise

    _sql, updates = apply_schema_pool.executemany.call_args.args
    obj_norm_written, org_norm_written, _ = updates[0]
    assert obj_norm_written is None
    assert org_norm_written == "camara municipal de campinas"

    # Phase 2: tender with objeto=None → dedup query skipped → normal INSERT path
    new_id = str(uuid.uuid4())
    inserted_row = _asyncpg_row({"id": new_id})
    conn = AsyncMock()

    async def _fetchrow(*args, **kwargs):
        sql = args[0] if args else ""
        if "INSERT INTO tenders" in sql:
            return inserted_row
        return None   # exact-key: not found; dedup: shouldn't be reached

    conn.fetchrow.side_effect = _fetchrow

    processor = TenderProcessor(_make_processor_pool(conn))

    with patch.object(processor, "_publish_es_event", new=AsyncMock()):
        await processor.process({
            "source":          "pncp",
            "external_id":     "PNCP-NULL-OBJ",
            "objeto":          None,
            "orgao":           "Câmara Municipal de Campinas",
            "data_publicacao": "2024-07-01",
        })

    # No cross-portal dedup SELECT should have been attempted
    dedup_calls = [
        c for c in conn.fetchrow.call_args_list
        if c.args
        and "SELECT" in c.args[0]
        and "objeto_norm" in c.args[0]
        and "source <>" in c.args[0]
    ]
    assert not dedup_calls, (
        "Cross-portal dedup SELECT was issued even though objeto_norm is None — "
        "it must be skipped when any key field is absent."
    )
