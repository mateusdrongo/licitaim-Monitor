"""
test_collector_access.py

Verifica que GET /api/collector/status aplica corretamente o controle de acesso:

- Requisição sem sessão (unauthenticated) → 401
- Usuário autenticado mas sem permissão de admin → 403
- Usuário admin válido → 200 com payload esperado

Nenhuma conexão real com banco é feita; todas as dependências externas são
substituídas por mocks em memória. Um app FastAPI mínimo (sem lifespan de
produção) é criado para que o TestClient não acione o scheduler/queue-worker.
"""
from __future__ import annotations

import os
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

# ── Garante que o pacote `app` seja importável sem instalação ─────────────────
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api.collector import router as collector_router  # noqa: E402
from app.core.deps import get_current_user               # noqa: E402


# ── App mínimo (sem lifespan de produção) ─────────────────────────────────────
# Criamos um app descartável que contém apenas o router do collector.
# Isso evita que o scheduler e o queue-worker do app de produção sejam
# iniciados, o que causa conflito de event loop no TestClient.

def _make_test_app() -> FastAPI:
    mini = FastAPI()
    mini.include_router(collector_router, prefix="/api")
    return mini


# ── Pool mínimo para o endpoint de status ─────────────────────────────────────

class _MinimalPool:
    """Retorna linhas vazias para todas as queries do endpoint /status."""

    async def fetch(self, query: str, *args):
        return []

    async def fetchrow(self, query: str, *args):
        return None

    async def execute(self, query: str, *args):
        pass


_MINIMAL_POOL = _MinimalPool()


# ── Dependências substitutas ───────────────────────────────────────────────────

def _raise_401():
    """Simula ausência de sessão — nenhum cookie presente."""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autenticado",
    )


def _regular_user() -> dict:
    """Usuário autenticado sem privilégio de admin."""
    return {"id": 99, "nome": "Usuário Comum", "email": "user@example.com"}


def _admin_user() -> dict:
    """Usuário autenticado com e-mail reconhecido como admin."""
    return {"id": 1, "nome": "Administrador", "email": "admin@example.com"}


# ── Fixture: pool mockado injetado em todos os testes ────────────────────────

@pytest.fixture(autouse=True)
def _mock_pool():
    # Patch at the import site so the collector endpoint uses the mock pool
    # regardless of how get_pool was imported into the module.
    with patch("app.api.collector.get_pool", new=AsyncMock(return_value=_MINIMAL_POOL)):
        yield


# ── Testes ────────────────────────────────────────────────────────────────────

class TestCollectorStatusAccessControl:
    """Testes de controle de acesso para GET /api/collector/status."""

    def test_unauthenticated_returns_401(self):
        """Requisição sem sessão deve ser rejeitada com 401 Unauthorized."""
        mini_app = _make_test_app()
        mini_app.dependency_overrides[get_current_user] = _raise_401

        with TestClient(mini_app, raise_server_exceptions=False) as client:
            response = client.get("/api/collector/status")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, (
            f"Esperava 401, recebeu {response.status_code}: {response.text}"
        )

    def test_non_admin_returns_403(self):
        """
        Usuário autenticado mas não-admin deve receber 403 Forbidden.
        ADMIN_EMAILS está definido e não inclui o e-mail do usuário.
        """
        mini_app = _make_test_app()
        mini_app.dependency_overrides[get_current_user] = _regular_user

        with patch.dict(os.environ, {"ADMIN_EMAILS": "admin@example.com"}):
            with TestClient(mini_app, raise_server_exceptions=False) as client:
                response = client.get("/api/collector/status")

        assert response.status_code == status.HTTP_403_FORBIDDEN, (
            f"Esperava 403, recebeu {response.status_code}: {response.text}"
        )
        detail = response.json().get("detail", "")
        assert "administradores" in detail.lower(), (
            f"Mensagem de erro inesperada: {detail!r}"
        )

    def test_admin_returns_200_with_expected_payload(self):
        """
        Usuário admin válido deve receber 200 com os campos esperados no payload.
        """
        mini_app = _make_test_app()
        mini_app.dependency_overrides[get_current_user] = _admin_user

        with patch.dict(os.environ, {"ADMIN_EMAILS": "admin@example.com"}):
            with TestClient(mini_app, raise_server_exceptions=False) as client:
                response = client.get("/api/collector/status")

        assert response.status_code == status.HTTP_200_OK, (
            f"Esperava 200, recebeu {response.status_code}: {response.text}"
        )
        payload = response.json()
        for field in ("last_run", "processed", "errors", "next_run_in",
                      "is_stale", "portals", "alert_state"):
            assert field in payload, (
                f"Campo '{field}' ausente na resposta: {list(payload.keys())}"
            )
        assert isinstance(payload["portals"], list)
        assert isinstance(payload["alert_state"], dict)

    def test_admin_email_case_insensitive(self):
        """
        A comparação de e-mail para admin deve ser case-insensitive.
        ADMIN_EMAILS em maiúsculas deve reconhecer o admin corretamente.
        """
        mini_app = _make_test_app()
        mini_app.dependency_overrides[get_current_user] = _admin_user

        # ADMIN_EMAILS em maiúsculas — user tem email em minúsculas
        with patch.dict(os.environ, {"ADMIN_EMAILS": "ADMIN@EXAMPLE.COM"}):
            with TestClient(mini_app, raise_server_exceptions=False) as client:
                response = client.get("/api/collector/status")

        assert response.status_code == status.HTTP_200_OK, (
            f"Comparação case-insensitive falhou: {response.status_code} {response.text}"
        )

    def test_admin_emails_not_configured_returns_503(self):
        """
        Quando ADMIN_EMAILS não está configurado (vazio), o endpoint deve
        retornar 503 Service Unavailable — endpoint administrativo desabilitado.
        """
        mini_app = _make_test_app()
        mini_app.dependency_overrides[get_current_user] = _admin_user

        env_without_admin = {k: v for k, v in os.environ.items() if k != "ADMIN_EMAILS"}
        with patch.dict(os.environ, env_without_admin, clear=True):
            with TestClient(mini_app, raise_server_exceptions=False) as client:
                response = client.get("/api/collector/status")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE, (
            f"Esperava 503 quando ADMIN_EMAILS ausente, "
            f"recebeu {response.status_code}: {response.text}"
        )
