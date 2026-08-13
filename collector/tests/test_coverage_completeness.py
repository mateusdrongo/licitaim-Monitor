"""
test_coverage_completeness.py — Verifies that is_complete in licitacoes_cache_coverage
is only True when all required portals succeed AND the canonical window is covered.

Scenarios tested:
  1. 30-day cycle, all portals succeed → is_complete=True
  2. 30-day cycle, PNCP portal fails (exception) → is_complete=False
  3. 30-day cycle, cache flush fails → is_complete=False
  4. 1-day cycle (default), all portals succeed → is_complete=False (window < 30d)
  5. Zero-result cycle → coverage still recorded (last_sync refreshed), is_complete=False
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── helpers ───────────────────────────────────────────────────────────────────

_OK_RESULT = {
    "processed": 5,
    "errors": 0,
    "cache_inserted": 3,
    "cache_updated": 2,
    "cache_write_failed": False,
    "changed_tenders": [],
}

_ZERO_RESULT = {
    "processed": 0,
    "errors": 0,
    "cache_inserted": 0,
    "cache_updated": 0,
    "cache_write_failed": False,
    "changed_tenders": [],
}

_CACHE_FAIL_RESULT = {
    "processed": 5,
    "errors": 0,
    "cache_inserted": 0,
    "cache_updated": 0,
    "cache_write_failed": True,   # rows_failed > 0 inside upsert_to_licitacoes_cache
    "changed_tenders": [],
}

_TENDER_ERRORS_RESULT = {
    "processed": 4,
    "errors": 1,              # at least one tender failed to process
    "cache_inserted": 3,
    "cache_updated": 1,
    "cache_write_failed": False,
    "changed_tenders": [],
}


def _mock_asyncpg_pool() -> MagicMock:
    """Return an asyncpg.Pool mock that does nothing when execute() is called."""
    pool = AsyncMock()
    pool.execute = AsyncMock(return_value=None)
    pool.close   = AsyncMock(return_value=None)
    return pool


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _patch_asyncpg_create_pool(monkeypatch):
    """
    Replace asyncpg.create_pool in standalone so tests never open a real DB.
    Returns the shared pool mock for further inspection if needed.
    """
    pool_mock = _mock_asyncpg_pool()
    monkeypatch.setattr(
        "collector.app.standalone.asyncpg.create_pool",
        AsyncMock(return_value=pool_mock),
    )
    return pool_mock


# ── tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_30d_cycle_all_portals_succeed_is_complete_true():
    """30-day cycle with no failures → is_complete=True."""
    recorded: list[dict] = []

    async def _record_coverage_spy(pool, total, data_ini, data_fim, is_complete=True):
        recorded.append({"total": total, "is_complete": is_complete})

    with (
        patch("collector.app.standalone.run_pncp_scrape", new=AsyncMock(return_value=_OK_RESULT)),
        patch("collector.app.standalone.run_comprasnet_scrape", new=AsyncMock(return_value=_OK_RESULT)),
        patch("collector.app.standalone.run_bec_sp_scrape", new=AsyncMock(return_value=_OK_RESULT)),
        patch("collector.app.standalone._write_collector_status", new=AsyncMock()),
        patch("collector.app.cache_writer.record_coverage", new=_record_coverage_spy),
        patch("collector.app.cache_writer.notify_favorites_changes", new=AsyncMock()),
    ):
        from collector.app.standalone import run_one_cycle

        result = await run_one_cycle(
            db_url="postgresql://fake",
            skip_comprasnet=False,
            skip_bec_sp=False,
            scrape_days=30,
        )

    assert result["is_complete"] is True
    assert len(recorded) > 0
    assert any(r["is_complete"] is True for r in recorded), \
        f"Expected at least one coverage record with is_complete=True; got {recorded}"


@pytest.mark.asyncio
async def test_30d_cycle_pncp_fails_is_complete_false():
    """30-day cycle where PNCP portal raises an exception → is_complete=False."""
    recorded: list[dict] = []

    async def _record_coverage_spy(pool, total, data_ini, data_fim, is_complete=True):
        recorded.append({"total": total, "is_complete": is_complete})

    with (
        patch("collector.app.standalone.run_pncp_scrape",
              new=AsyncMock(side_effect=RuntimeError("PNCP timeout"))),
        patch("collector.app.standalone.run_comprasnet_scrape", new=AsyncMock(return_value=_OK_RESULT)),
        patch("collector.app.standalone.run_bec_sp_scrape", new=AsyncMock(return_value=_OK_RESULT)),
        patch("collector.app.standalone._write_collector_status", new=AsyncMock()),
        patch("collector.app.cache_writer.record_coverage", new=_record_coverage_spy),
        patch("collector.app.cache_writer.notify_favorites_changes", new=AsyncMock()),
    ):
        from collector.app.standalone import run_one_cycle

        result = await run_one_cycle(
            db_url="postgresql://fake",
            skip_comprasnet=False,
            skip_bec_sp=False,
            scrape_days=30,
        )

    assert result["is_complete"] is False, \
        "PNCP portal failure must set is_complete=False"
    # Coverage must still be recorded (to refresh last_sync)
    assert len(recorded) > 0, "record_coverage must be called even after a portal failure"
    assert all(not r["is_complete"] for r in recorded), \
        f"All coverage records must have is_complete=False; got {recorded}"


@pytest.mark.asyncio
async def test_30d_cycle_cache_flush_fails_is_complete_false():
    """30-day cycle where cache writes fail → is_complete=False."""
    recorded: list[dict] = []

    async def _record_coverage_spy(pool, total, data_ini, data_fim, is_complete=True):
        recorded.append({"total": total, "is_complete": is_complete})

    with (
        patch("collector.app.standalone.run_pncp_scrape",
              new=AsyncMock(return_value=_CACHE_FAIL_RESULT)),
        patch("collector.app.standalone.run_comprasnet_scrape", new=AsyncMock(return_value=_OK_RESULT)),
        patch("collector.app.standalone.run_bec_sp_scrape", new=AsyncMock(return_value=_OK_RESULT)),
        patch("collector.app.standalone._write_collector_status", new=AsyncMock()),
        patch("collector.app.cache_writer.record_coverage", new=_record_coverage_spy),
        patch("collector.app.cache_writer.notify_favorites_changes", new=AsyncMock()),
    ):
        from collector.app.standalone import run_one_cycle

        result = await run_one_cycle(
            db_url="postgresql://fake",
            skip_comprasnet=False,
            skip_bec_sp=False,
            scrape_days=30,
        )

    assert result["is_complete"] is False, \
        "Cache write failure must set is_complete=False"
    assert all(not r["is_complete"] for r in recorded), \
        f"All coverage records must have is_complete=False; got {recorded}"


@pytest.mark.asyncio
async def test_1d_cycle_all_portals_succeed_is_complete_false():
    """Default 1-day cycle (SCRAPE_DAYS=1) — window < 30d → is_complete=False."""
    recorded: list[dict] = []

    async def _record_coverage_spy(pool, total, data_ini, data_fim, is_complete=True):
        recorded.append({"total": total, "is_complete": is_complete})

    with (
        patch("collector.app.standalone.run_pncp_scrape", new=AsyncMock(return_value=_OK_RESULT)),
        patch("collector.app.standalone.run_comprasnet_scrape", new=AsyncMock(return_value=_OK_RESULT)),
        patch("collector.app.standalone.run_bec_sp_scrape", new=AsyncMock(return_value=_OK_RESULT)),
        patch("collector.app.standalone._write_collector_status", new=AsyncMock()),
        patch("collector.app.cache_writer.record_coverage", new=_record_coverage_spy),
        patch("collector.app.cache_writer.notify_favorites_changes", new=AsyncMock()),
    ):
        from collector.app.standalone import run_one_cycle

        result = await run_one_cycle(
            db_url="postgresql://fake",
            skip_comprasnet=False,
            skip_bec_sp=False,
            scrape_days=1,          # default — only 1 day
        )

    assert result["is_complete"] is False, \
        "1-day scrape must not claim global 30-day coverage"
    assert all(not r["is_complete"] for r in recorded), \
        f"All coverage records must have is_complete=False for 1-day window; got {recorded}"


@pytest.mark.asyncio
async def test_30d_cycle_tender_errors_is_complete_false():
    """30-day cycle where individual tenders fail (errors > 0) → is_complete=False."""
    recorded: list[dict] = []

    async def _record_coverage_spy(pool, total, data_ini, data_fim, is_complete=True):
        recorded.append({"total": total, "is_complete": is_complete})

    with (
        patch("collector.app.standalone.run_pncp_scrape",
              new=AsyncMock(return_value=_TENDER_ERRORS_RESULT)),
        patch("collector.app.standalone.run_comprasnet_scrape", new=AsyncMock(return_value=_OK_RESULT)),
        patch("collector.app.standalone.run_bec_sp_scrape", new=AsyncMock(return_value=_OK_RESULT)),
        patch("collector.app.standalone._write_collector_status", new=AsyncMock()),
        patch("collector.app.cache_writer.record_coverage", new=_record_coverage_spy),
        patch("collector.app.cache_writer.notify_favorites_changes", new=AsyncMock()),
    ):
        from collector.app.standalone import run_one_cycle

        result = await run_one_cycle(
            db_url="postgresql://fake",
            skip_comprasnet=False,
            skip_bec_sp=False,
            scrape_days=30,
        )

    assert result["is_complete"] is False, \
        "Tender-level errors must set is_complete=False (data may be incomplete)"
    assert all(not r["is_complete"] for r in recorded), \
        f"All coverage records must have is_complete=False; got {recorded}"


@pytest.mark.asyncio
async def test_zero_result_cycle_still_records_coverage():
    """
    A cycle that finds no new tenders (zero-result, e.g. weekend or portal down)
    must still call record_coverage to refresh last_sync in the DB.
    """
    recorded: list[dict] = []

    async def _record_coverage_spy(pool, total, data_ini, data_fim, is_complete=True):
        recorded.append({"total": total, "is_complete": is_complete})

    with (
        patch("collector.app.standalone.run_pncp_scrape", new=AsyncMock(return_value=_ZERO_RESULT)),
        patch("collector.app.standalone.run_comprasnet_scrape", new=AsyncMock(return_value=_ZERO_RESULT)),
        patch("collector.app.standalone.run_bec_sp_scrape", new=AsyncMock(return_value=_ZERO_RESULT)),
        patch("collector.app.standalone._write_collector_status", new=AsyncMock()),
        patch("collector.app.cache_writer.record_coverage", new=_record_coverage_spy),
        patch("collector.app.cache_writer.notify_favorites_changes", new=AsyncMock()),
    ):
        from collector.app.standalone import run_one_cycle

        result = await run_one_cycle(
            db_url="postgresql://fake",
            skip_comprasnet=False,
            skip_bec_sp=False,
            scrape_days=30,
        )

    # Coverage must be recorded even with zero results
    assert len(recorded) > 0, \
        "record_coverage must be called even when no tenders were found"
    # Zero results + no failures → still marked complete if window >= 30d
    assert any(r["is_complete"] is True for r in recorded), \
        "Zero-result cycle with full 30d window and no errors should be is_complete=True"
    assert result["cache_inserted"] == 0
    assert result["cache_updated"]  == 0
