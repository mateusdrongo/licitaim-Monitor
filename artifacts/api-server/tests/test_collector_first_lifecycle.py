"""
test_collector_first_lifecycle.py — Verifies that the collector-first architecture
contract is upheld: the API never calls external data sources directly, either at
startup (warm-up) or via the manual sync endpoint (/admin/sync, /collector/run).

Strategy: use source-code inspection (inspect.getsource / file reads) rather than
import-and-run so we avoid the real DB that live modules require.

Invariants tested:
  1. main.py does not import sync_licitacoes_job at module level.
  2. The warm-up block in main.py does not call asyncio.create_task.
  3. _run_collection_cycle delegates to run_one_cycle (no direct scraper calls).
  4. manual_sync delegates via _col_mod (no direct scraper/sync_job calls).
  5. /collector/run (_run_collection_cycle) does not duplicate per-portal orchestration.
  6. run_one_cycle calls record_coverage and notify_favorites_changes.
  7. licitacoes.py does not call record_coverage or notify_favorites_changes.
"""
from __future__ import annotations

import pathlib
import pytest

# Paths relative to workspace root
_ROOT = pathlib.Path(__file__).parent.parent.parent.parent  # workspace root
_API_DIR = _ROOT / "artifacts" / "api-server" / "app"
_COLLECTOR_STANDALONE = _ROOT / "collector" / "app" / "standalone.py"


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


# ── 1. main.py must not import sync_licitacoes_job ───────────────────────────

def test_main_py_does_not_import_sync_licitacoes_job():
    """main.py warm-up must not reference sync_licitacoes_job."""
    src = _read(_API_DIR / "main.py")
    assert "sync_licitacoes_job" not in src, (
        "main.py still imports or calls sync_licitacoes_job — "
        "the warm-up must not trigger direct external sync on empty cache."
    )


# ── 2. main.py warm-up must not create a background task ─────────────────────

def test_main_py_warm_up_does_not_call_create_task_for_sync():
    """
    The warm-up block in main.py must not call asyncio.create_task with any
    sync or scrape function when the cache is empty.
    """
    src = _read(_API_DIR / "main.py")
    # The lifespan section between the warm-up comment and the misfire-recovery
    # comment must not contain asyncio.create_task paired with any sync/scrape call.
    # We verify by checking that 'create_task' does not appear alongside 'sync' or 'scrape'
    # within the warm-up comment block.
    warm_up_section = ""
    in_warm_up = False
    for line in src.splitlines():
        if "licitacoes_cache vazio" in line or "Warm-up" in line:
            in_warm_up = True
        if in_warm_up and "Misfire recovery" in line:
            break
        if in_warm_up:
            warm_up_section += line + "\n"

    assert "create_task" not in warm_up_section, (
        "The warm-up block in main.py must not call asyncio.create_task — "
        "an empty cache is handled by the collector standalone, not by the API."
        f"\n\nWarm-up section found:\n{warm_up_section}"
    )


# ── 3. _run_collection_cycle uses run_one_cycle, not direct scrapers ──────────

def test_run_collection_cycle_delegates_to_run_one_cycle():
    """
    The _run_collection_cycle function (used by /collector/run and /admin/sync)
    must delegate to run_one_cycle(); it must not orchestrate portals directly.
    """
    src = _read(_API_DIR / "api" / "collector.py")

    # Extract just the _run_collection_cycle function body
    lines = src.splitlines()
    in_func = False
    func_body = []
    for line in lines:
        if "async def _run_collection_cycle" in line:
            in_func = True
        if in_func:
            func_body.append(line)
            # Stop at next top-level async def / def
            if len(func_body) > 1 and (
                line.startswith("async def ")
                or line.startswith("def ")
                or line.startswith("@router")
            ):
                func_body.pop()
                break
    body = "\n".join(func_body)

    assert "run_one_cycle" in body, (
        "_run_collection_cycle must call run_one_cycle(); "
        "direct scraper orchestration found instead."
    )
    assert "run_pncp_scrape" not in body, (
        "_run_collection_cycle must not call run_pncp_scrape directly — "
        "portal orchestration belongs inside run_one_cycle()."
    )
    assert "run_comprasnet_scrape" not in body, (
        "_run_collection_cycle must not call run_comprasnet_scrape directly."
    )
    assert "run_bec_sp_scrape" not in body, (
        "_run_collection_cycle must not call run_bec_sp_scrape directly."
    )
    assert "sync_licitacoes_job" not in body, (
        "_run_collection_cycle must not call sync_licitacoes_job."
    )


# ── 4. manual_sync delegates via _col_mod ─────────────────────────────────────

def test_manual_sync_handler_delegates_via_col_mod():
    """
    The manual_sync handler in licitacoes.py must not reference PNCP scrapers or
    sync_licitacoes_job; it must delegate via _col_mod (the collector API module).
    """
    src = _read(_API_DIR / "api" / "licitacoes.py")

    # Extract manual_sync function body
    lines = src.splitlines()
    in_func = False
    func_body = []
    for line in lines:
        if "async def manual_sync" in line:
            in_func = True
        if in_func:
            func_body.append(line)
            if len(func_body) > 1 and (
                line.startswith("async def ")
                or line.startswith("def ")
                or line.startswith("@router")
            ):
                func_body.pop()
                break
    body = "\n".join(func_body)

    assert "sync_licitacoes_job" not in body, (
        "manual_sync must not reference sync_licitacoes_job."
    )
    assert "run_pncp_scrape" not in body, (
        "manual_sync must not call run_pncp_scrape directly."
    )
    assert "_col_mod" in body or "_run_collection_cycle" in body, (
        "manual_sync must delegate to the collector module (_col_mod)."
    )


# ── 5. /collector/run endpoint body is clean ─────────────────────────────────

def test_collector_run_endpoint_body_has_no_direct_scraper_imports():
    """
    The @router.post('/run') endpoint handler (collector_run) in collector.py
    must not contain duplicated per-portal orchestration — it just enqueues
    _run_collection_cycle as a BackgroundTask.
    """
    src = _read(_API_DIR / "api" / "collector.py")
    # The endpoint function itself (collector_run) is small; verify it doesn't
    # inline PNCP calls.
    lines = src.splitlines()
    in_func = False
    func_body = []
    for line in lines:
        if "async def collector_run" in line:
            in_func = True
        if in_func:
            func_body.append(line)
            if len(func_body) > 1 and (
                line.startswith("async def ")
                or line.startswith("def ")
                or line.startswith("@router")
            ):
                func_body.pop()
                break
    body = "\n".join(func_body)

    assert "run_pncp_scrape" not in body, \
        "collector_run endpoint must not call run_pncp_scrape directly."
    assert "sync_licitacoes_job" not in body, \
        "collector_run endpoint must not call sync_licitacoes_job."


# ── 6. run_one_cycle is the unified orchestration entry point ─────────────────

def test_run_one_cycle_covers_cache_and_notifications():
    """run_one_cycle must call record_coverage and notify_favorites_changes."""
    src = _read(_COLLECTOR_STANDALONE)
    # Extract just run_one_cycle
    lines = src.splitlines()
    in_func = False
    func_body = []
    for line in lines:
        if "async def run_one_cycle" in line:
            in_func = True
        if in_func:
            func_body.append(line)
            if len(func_body) > 1 and line.startswith("async def "):
                func_body.pop()
                break
    body = "\n".join(func_body)

    assert "record_coverage" in body, \
        "run_one_cycle must call record_coverage after each cycle."
    assert "notify_favorites_changes" in body, \
        "run_one_cycle must call notify_favorites_changes for changed tenders."


# ── 7. licitacoes.py must not touch collector internals ──────────────────────

def test_licitacoes_api_does_not_call_collector_internals():
    """
    licitacoes.py must not import or call record_coverage or
    notify_favorites_changes — only the collector's run_one_cycle does that.
    """
    src = _read(_API_DIR / "api" / "licitacoes.py")

    assert "record_coverage" not in src, \
        "licitacoes.py must not call record_coverage (collector-only concern)."
    assert "notify_favorites_changes" not in src, \
        "licitacoes.py must not call notify_favorites_changes (collector-only)."
