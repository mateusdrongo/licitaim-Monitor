"""
test_tarefa_prazo_validation.py

Confirms that TarefaCreate and TarefaUpdate enforce strict ISO-8601 date
validation on the `prazo` field via StrictDateMixin:

- Malformed strings (e.g. "2026-07-17 garbage") → HTTP 422 with the
  Portuguese "Formato de data não reconhecido" message.
- Valid plain dates ("2026-07-17") and datetime strings with offsets
  ("2026-07-17T08:00:00+00:00") and Z suffix ("2026-07-17T08:00:00Z")
  pass validation (no 422).
- null / absent prazo is accepted.

All DB I/O is mocked; no real database is required.
"""
from __future__ import annotations

import os
import sys
import pytest
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure the `app` package is importable without installation
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api.gerenciamento import router as ger_router  # noqa: E402
from app.core.deps import get_current_user              # noqa: E402


# ── Minimal test app ──────────────────────────────────────────────────────────

def _make_app() -> FastAPI:
    mini = FastAPI()
    # The router already carries prefix="/gerenciamento"; register it under "/api"
    # so routes land at /api/gerenciamento/{id}/tarefas as expected.
    mini.include_router(ger_router, prefix="/api")
    return mini


def _current_user() -> dict:
    return {"id": 42, "nome": "Test User", "email": "test@example.com"}


# ── Mock pool ─────────────────────────────────────────────────────────────────

class _FakePool:
    """
    Returns plausible stub rows for the two queries inside create_tarefa /
    update_tarefa:
      1. _assert_ger  → fetchrow on licitacoes_gerenciadas — must not be None
      2. INSERT / UPDATE tarefas  → fetchrow — returns a minimal tarefa row
    """

    def __init__(self):
        # Used to switch the second fetchrow between insert and update shapes
        self._call_count = 0

    async def fetchrow(self, query: str, *args):
        self._call_count += 1
        if self._call_count == 1:
            # _assert_ger — just needs a truthy result
            row = MagicMock()
            row.__getitem__ = lambda self, k: 1
            return row
        # INSERT/UPDATE tarefa row
        r = {
            "id": 1,
            "gerenciamento_id": 1,
            "titulo": "Tarefa teste",
            "descricao": None,
            "prazo": date(2026, 7, 17),
            "concluida": False,
            "prioridade": "normal",
            "categoria": "geral",
            "concluida_em": None,
            "criado_em": None,
            "atualizado_em": None,
        }
        return r

    async def fetch(self, query: str, *args):
        return []

    async def execute(self, query: str, *args):
        pass


# ── Helper: build a fresh client for each test ───────────────────────────────

def _client() -> TestClient:
    app = _make_app()
    app.dependency_overrides[get_current_user] = _current_user
    return TestClient(app, raise_server_exceptions=False)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _mock_pool():
    """Patch get_pool for the gerenciamento module so no real DB is needed."""
    with patch(
        "app.api.gerenciamento.get_pool",
        new=AsyncMock(side_effect=lambda: _FakePool()),
    ):
        yield


# ── POST /api/gerenciamento/{id}/tarefas ─────────────────────────────────────

class TestTarefaCreatePrazo:
    """TarefaCreate.prazo validation via POST /api/gerenciamento/{id}/tarefas"""

    def _post(self, prazo_value) -> "TestClient":
        return _client().post(
            "/api/gerenciamento/1/tarefas",
            json={"titulo": "Tarefa teste", "prazo": prazo_value},
        )

    # ── Bad dates ─────────────────────────────────────────────────────────────

    def test_garbage_suffix_returns_422(self):
        """'2026-07-17 garbage' must be rejected with 422."""
        resp = self._post("2026-07-17 garbage")
        assert resp.status_code == 422, resp.text
        body = resp.json()
        detail_str = str(body.get("detail", ""))
        assert "Formato de data não reconhecido" in detail_str, (
            f"Mensagem de erro inesperada: {detail_str!r}"
        )

    def test_incomplete_datetime_returns_422(self):
        """'2026-07-17T' (truncated ISO datetime) must be rejected."""
        resp = self._post("2026-07-17T")
        assert resp.status_code == 422, resp.text
        detail_str = str(resp.json().get("detail", ""))
        assert "Formato de data não reconhecido" in detail_str, (
            f"Mensagem de erro inesperada: {detail_str!r}"
        )

    def test_nonsense_string_returns_422(self):
        """A completely invalid string must be rejected."""
        resp = self._post("not-a-date")
        assert resp.status_code == 422, resp.text
        detail_str = str(resp.json().get("detail", ""))
        assert "Formato de data não reconhecido" in detail_str, (
            f"Mensagem de erro inesperada: {detail_str!r}"
        )

    # ── Valid dates ───────────────────────────────────────────────────────────

    def test_plain_date_accepted(self):
        """'2026-07-17' (plain ISO date) must be accepted — no 422."""
        resp = self._post("2026-07-17")
        assert resp.status_code != 422, (
            f"Data ISO válida rejeitada: {resp.text}"
        )

    def test_datetime_with_offset_accepted(self):
        """'2026-07-17T08:00:00+00:00' must be accepted — no 422."""
        resp = self._post("2026-07-17T08:00:00+00:00")
        assert resp.status_code != 422, (
            f"Datetime com offset rejeitado: {resp.text}"
        )

    def test_datetime_with_z_suffix_accepted(self):
        """'2026-07-17T08:00:00Z' must be accepted — no 422."""
        resp = self._post("2026-07-17T08:00:00Z")
        assert resp.status_code != 422, (
            f"Datetime com sufixo Z rejeitado: {resp.text}"
        )

    def test_null_prazo_accepted(self):
        """null prazo must be accepted (field is optional)."""
        resp = self._post(None)
        assert resp.status_code != 422, (
            f"prazo=null rejeitado: {resp.text}"
        )

    def test_absent_prazo_accepted(self):
        """Missing prazo key must be accepted (field has default None)."""
        client = _client()
        resp = client.post(
            "/api/gerenciamento/1/tarefas",
            json={"titulo": "Sem prazo"},
        )
        assert resp.status_code != 422, (
            f"prazo ausente rejeitado: {resp.text}"
        )


# ── PATCH /api/gerenciamento/{id}/tarefas/{tid} ──────────────────────────────

class TestTarefaUpdatePrazo:
    """TarefaUpdate.prazo validation via PATCH /api/gerenciamento/{id}/tarefas/{tid}"""

    def _patch(self, prazo_value) -> "TestClient":
        return _client().patch(
            "/api/gerenciamento/1/tarefas/1",
            json={"prazo": prazo_value},
        )

    # ── Bad dates ─────────────────────────────────────────────────────────────

    def test_garbage_suffix_returns_422(self):
        """'2026-07-17 garbage' on PATCH must be rejected with 422."""
        resp = self._patch("2026-07-17 garbage")
        assert resp.status_code == 422, resp.text
        detail_str = str(resp.json().get("detail", ""))
        assert "Formato de data não reconhecido" in detail_str, (
            f"Mensagem de erro inesperada: {detail_str!r}"
        )

    def test_nonsense_string_returns_422(self):
        """A completely invalid string on PATCH must be rejected."""
        resp = self._patch("nonsense")
        assert resp.status_code == 422, resp.text
        detail_str = str(resp.json().get("detail", ""))
        assert "Formato de data não reconhecido" in detail_str, (
            f"Mensagem de erro inesperada: {detail_str!r}"
        )

    # ── Valid dates ───────────────────────────────────────────────────────────

    def test_plain_date_accepted(self):
        """'2026-08-01' on PATCH must be accepted — no 422."""
        resp = self._patch("2026-08-01")
        assert resp.status_code != 422, (
            f"Data ISO válida rejeitada no PATCH: {resp.text}"
        )

    def test_datetime_with_offset_accepted(self):
        """'2026-08-01T09:00:00+00:00' on PATCH must be accepted."""
        resp = self._patch("2026-08-01T09:00:00+00:00")
        assert resp.status_code != 422, (
            f"Datetime com offset rejeitado no PATCH: {resp.text}"
        )

    def test_null_prazo_accepted(self):
        """null prazo on PATCH must be accepted."""
        resp = self._patch(None)
        # null prazo with no other fields → 400 "Nenhum campo para atualizar"
        # but NOT 422 (the value itself is valid)
        assert resp.status_code != 422, (
            f"prazo=null rejeitado no PATCH: {resp.text}"
        )
