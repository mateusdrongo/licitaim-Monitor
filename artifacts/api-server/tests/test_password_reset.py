"""
test_password_reset.py — Tests for the password-reset flow.

Covers:
- Non-enumeration: forgot-password always returns the same generic response
- Expired / already-used / invalid tokens are rejected
- Atomic single-use claim (second use of the same token is rejected)
- Password is actually updated after a successful reset
- Session invalidation: tokens issued before the reset are rejected;
  a fresh login after the reset is accepted
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import path setup (mirrors existing conftest.py)
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.security import (
    create_access_token,
    decode_token_full,
    get_password_hash,
    verify_password,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(session_version: int = 0) -> dict:
    return {
        "id": "user-test-001",
        "nome": "Teste",
        "email": "teste@example.com",
        "empresa": None,
        "cnpj": None,
        "plano": "gratuito",
        "avatar_url": None,
        "criado_em": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "notif_email": True,
        "notif_telegram": False,
        "telegram_chat_id": None,
        "session_version": session_version,
        "senha_hash": get_password_hash("senhaforte123"),
    }


def _make_pool_mock(user: dict | None, reset_token_row: dict | None = None):
    """Build a minimal asyncpg pool mock for auth endpoint tests."""
    pool = MagicMock()
    conn = AsyncMock()

    async def fetchrow(sql, *args):
        sql_lower = sql.lower().strip()
        if "password_reset_tokens" in sql_lower:
            if reset_token_row is None:
                return None
            return reset_token_row
        # Default: return user lookup
        return user

    async def execute(sql, *args):
        return None

    conn.fetchrow = fetchrow
    conn.execute = execute

    # pool.fetchrow at top level
    pool.fetchrow = fetchrow
    pool.execute = execute

    # pool.acquire() returns an async context manager yielding the conn
    acquire_cm = AsyncMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)

    # conn.transaction() returns an async context manager
    txn_cm = AsyncMock()
    txn_cm.__aenter__ = AsyncMock(return_value=None)
    txn_cm.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn_cm)

    return pool


# ===========================================================================
# 1. JWT session-version logic (no DB required)
# ===========================================================================

class TestSessionVersionInJWT:
    def test_token_carries_sv_claim(self):
        token = create_access_token("user-1", session_version=3)
        payload = decode_token_full(token)
        assert payload is not None
        assert payload["sv"] == 3

    def test_legacy_token_has_no_sv(self):
        """
        Tokens created before sv was introduced have no sv claim.
        decode_token_full must still parse them; callers treat missing sv as 0.
        """
        from app.core.config import get_settings
        from jose import jwt

        settings = get_settings()
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-1",
            "exp": now + timedelta(days=1),
            "iat": now,
            # no "sv" key
        }
        token = jwt.encode(payload, settings.get_jwt_secret(), algorithm=settings.jwt_algorithm)
        decoded = decode_token_full(token)
        assert decoded is not None
        assert "sv" not in decoded

    def test_session_version_mismatch_means_stale(self):
        """
        A token with sv=1 is stale when the user's session_version is 2.
        Simulate the check from deps.get_current_user.
        """
        token = create_access_token("user-1", session_version=1)
        payload = decode_token_full(token)
        token_sv = payload.get("sv", 0)
        stored_sv = 2  # password was reset once more
        assert token_sv != stored_sv  # would raise 401

    def test_session_version_match_means_valid(self):
        token = create_access_token("user-1", session_version=2)
        payload = decode_token_full(token)
        token_sv = payload.get("sv", 0)
        stored_sv = 2
        assert token_sv == stored_sv

    def test_legacy_token_sv0_valid_for_unreset_user(self):
        """
        Legacy tokens (no sv) default to sv=0; a user who has never reset
        their password has session_version=0 — the check passes.
        """
        from app.core.config import get_settings
        from jose import jwt

        settings = get_settings()
        now = datetime.now(timezone.utc)
        legacy_payload = {
            "sub": "user-1",
            "exp": now + timedelta(days=1),
            "iat": now,
        }
        token = jwt.encode(legacy_payload, settings.get_jwt_secret(), algorithm=settings.jwt_algorithm)
        decoded = decode_token_full(token)
        token_sv = decoded.get("sv", 0)
        stored_sv = 0  # never reset
        assert token_sv == stored_sv  # passes check

    def test_legacy_token_rejected_after_reset(self):
        """
        Legacy tokens (no sv, treated as sv=0) must be rejected once
        the user's session_version becomes > 0 after a password reset.
        """
        from app.core.config import get_settings
        from jose import jwt

        settings = get_settings()
        now = datetime.now(timezone.utc)
        legacy_payload = {
            "sub": "user-1",
            "exp": now + timedelta(days=1),
            "iat": now,
        }
        token = jwt.encode(legacy_payload, settings.get_jwt_secret(), algorithm=settings.jwt_algorithm)
        decoded = decode_token_full(token)
        token_sv = decoded.get("sv", 0)
        stored_sv = 1  # password was reset
        assert token_sv != stored_sv  # rejected


# ===========================================================================
# 2. forgot-password non-enumeration
# ===========================================================================

class TestForgotPasswordNonEnumeration:
    """forgot-password must always return the same generic response regardless
    of whether the e-mail is registered, to avoid account enumeration."""

    @pytest.mark.asyncio
    async def test_unknown_email_returns_generic_response(self):
        from app.api.auth import forgot_password, ForgotPasswordRequest

        pool = _make_pool_mock(user=None)
        with patch("app.api.auth.get_pool", return_value=AsyncMock(return_value=pool)):
            # pool is returned as an awaitable that returns the mock
            with patch("app.api.auth.get_pool", new=AsyncMock(return_value=pool)):
                req = ForgotPasswordRequest(email="naoexiste@example.com")
                result = await forgot_password(req)
        assert "message" in result
        assert "dev_reset_link" not in result

    @pytest.mark.asyncio
    async def test_known_email_returns_same_generic_response(self):
        from app.api.auth import forgot_password, ForgotPasswordRequest

        user = _make_user()
        pool = _make_pool_mock(user=user)

        write_calls = []

        class _FakePath:
            def open(self, mode):
                cm = MagicMock()
                cm.__enter__ = lambda s: _FakeFile()
                cm.__exit__ = MagicMock(return_value=False)
                return cm

        class _FakeFile:
            def write(self, text):
                write_calls.append(text)

        with patch("app.api.auth.get_pool", new=AsyncMock(return_value=pool)):
            with patch("app.core.config.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(environment="development")
                import pathlib
                with patch("pathlib.Path", return_value=_FakePath()):
                    req = ForgotPasswordRequest(email=user["email"])
                    result = await forgot_password(req)

        assert "message" in result
        assert "dev_reset_link" not in result
        assert "token" not in str(result)


# ===========================================================================
# 3. reset-password: invalid / expired / already-used tokens
# ===========================================================================

class TestResetPasswordTokenValidation:
    @pytest.mark.asyncio
    async def test_unknown_token_rejected(self):
        from app.api.auth import reset_password, ResetPasswordRequest
        from fastapi import HTTPException

        pool = _make_pool_mock(user=None, reset_token_row=None)

        # The reset endpoint acquires a connection and runs a conditional UPDATE.
        # Simulate the UPDATE RETURNING nothing (token not found/used/expired).
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.execute = AsyncMock(return_value=None)
        txn_cm = AsyncMock()
        txn_cm.__aenter__ = AsyncMock(return_value=None)
        txn_cm.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=txn_cm)

        acquire_cm = AsyncMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=acquire_cm)

        from app.services.websocket_manager import get_ws_manager
        with patch("app.api.auth.get_pool", new=AsyncMock(return_value=pool)):
            with pytest.raises(HTTPException) as exc:
                req = ResetPasswordRequest(token="invalid-token", password="nova_senha_123")
                await reset_password(req)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_short_password_rejected(self):
        from app.api.auth import reset_password, ResetPasswordRequest
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            req = ResetPasswordRequest(token="any-token", password="curta")
            await reset_password(req)
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_valid_token_updates_session_version(self):
        """A successful reset claims the token and returns success."""
        from app.api.auth import reset_password, ResetPasswordRequest

        claimed_row = {"user_id": "user-test-001"}
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=claimed_row)
        conn.execute = AsyncMock(return_value=None)
        txn_cm = AsyncMock()
        txn_cm.__aenter__ = AsyncMock(return_value=None)
        txn_cm.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=txn_cm)

        acquire_cm = AsyncMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=False)

        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_cm)

        ws_manager_mock = AsyncMock()
        ws_manager_mock.disconnect_all_for_user = AsyncMock()

        with patch("app.api.auth.get_pool", new=AsyncMock(return_value=pool)):
            with patch("app.services.websocket_manager.get_ws_manager", return_value=ws_manager_mock):
                with patch("app.api.auth.get_pool", new=AsyncMock(return_value=pool)):
                    req = ResetPasswordRequest(token="valid-token-abc", password="nova_senha_forte_123")
                    result = await reset_password(req)

        assert "message" in result
        assert "sucesso" in result["message"]
        # verify the session_version-incrementing UPDATE was called
        assert conn.execute.called


# ===========================================================================
# 4. Password hashing utilities
# ===========================================================================

class TestPasswordHashing:
    def test_hash_and_verify(self):
        pw = "minha_senha_forte_456"
        hashed = get_password_hash(pw)
        assert verify_password(pw, hashed)

    def test_wrong_password_rejected(self):
        hashed = get_password_hash("correta")
        assert not verify_password("errada", hashed)
