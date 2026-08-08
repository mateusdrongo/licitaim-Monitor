"""
test_telegram_chat_id_e2e.py

End-to-end tests confirming that:
1. PATCH /auth/me persists telegram_chat_id in the database.
2. _resolve_channels includes the telegram channel when notif_telegram=True.
3. send() passes the correct chat_id to send_telegram for a user with
   notif_telegram=True and telegram_chat_id set.
4. send_tender_update() fires the Telegram delivery path with the correct
   chat_id when the user has a favorited tender that changes.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

NOTIF_MODULE = "app.services.notification_service"
TG_MODULE    = "app.services.senders.telegram_sender"
DB_SESSION_MOD = "app.db.session"


# ── helpers ───────────────────────────────────────────────────────────────────

class _FakeRecord(dict):
    """
    Minimal asyncpg-Record-like object that survives dict() conversion.
    asyncpg records support both mapping and attribute access; dict() works
    because they expose keys() + __getitem__, which dict() uses internally.
    """
    pass


def _telegram_user(**overrides) -> dict:
    """User with Telegram notifications enabled and a chat_id set."""
    base = {
        "id": "user-tg-123",
        "email": "tg@example.com",
        "notif_push": False,
        "notif_email": False,
        "notif_whatsapp": False,
        "notif_telegram": True,
        "telegram_chat_id": "987654321",
    }
    base.update(overrides)
    return base


def _tender(**overrides) -> dict:
    base = {
        "id": "LICIT-TG-001",
        "objeto": "Aquisição de equipamentos de TI",
        "orgao": "Ministério da Educação",
        "uf": "DF",
        "valorEstimado": 500000.0,
        "source": "pncp",
    }
    base.update(overrides)
    return base


def _make_pool() -> MagicMock:
    pool = MagicMock()
    pool.execute  = AsyncMock(return_value="OK")
    # Return a non-None row_id to simulate a successful INSERT RETURNING id.
    # send_tender_update uses pool.fetchval (not pool.execute) for its dedup INSERT.
    pool.fetchval = AsyncMock(return_value=1)
    pool.acquire  = MagicMock()
    pool.fetchrow = AsyncMock(return_value=None)

    conn = MagicMock()
    conn.execute = AsyncMock(return_value="OK")
    conn.transaction = MagicMock()

    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__  = AsyncMock(return_value=False)
    conn.transaction.return_value = tx

    acq = MagicMock()
    acq.__aenter__ = AsyncMock(return_value=conn)
    acq.__aexit__  = AsyncMock(return_value=False)
    pool.acquire.return_value = acq

    return pool


# ============================================================================
# PATCH /auth/me — telegram_chat_id persistence
# ============================================================================

class TestPatchMeTelegramChatId:
    """PATCH /auth/me must persist telegram_chat_id to the database."""

    @pytest.mark.asyncio
    async def test_patch_me_saves_telegram_chat_id(self):
        """
        PATCH /auth/me with telegram_chat_id triggers an UPDATE that includes
        the telegram_chat_id column and returns the saved value.
        """
        pool = _make_pool()

        saved_row = _FakeRecord({
            "id": "user-tg-123",
            "nome": "Teste TG",
            "email": "tg@example.com",
            "empresa": None,
            "cnpj": None,
            "plano": "profissional",
            "avatar_url": None,
            "criado_em": None,
            "notif_email": True,
            "notif_telegram": True,
            "telegram_chat_id": "987654321",
        })
        pool.fetchrow = AsyncMock(return_value=saved_row)

        current_user = {
            "id": "user-tg-123",
            "nome": "Teste TG",
            "email": "tg@example.com",
            "empresa": None,
            "cnpj": None,
            "plano": "profissional",
            "avatar_url": None,
            "criado_em": None,
            "notif_email": True,
            "notif_telegram": True,
            "telegram_chat_id": None,
        }

        with patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)):
            from app.api.auth import update_me, ProfileUpdate
            body = ProfileUpdate(telegram_chat_id="987654321", notif_telegram=True)
            result = await update_me(body=body, current_user=current_user)

        # The UPDATE must have been called once
        pool.fetchrow.assert_awaited_once()
        call_args = pool.fetchrow.call_args

        # First positional arg is the SQL string
        sql = call_args[0][0]
        assert "telegram_chat_id" in sql, (
            "UPDATE query must reference telegram_chat_id column"
        )

        # The returned dict must expose the saved chat ID
        assert result.get("telegramChatId") == "987654321", (
            f"Expected telegramChatId='987654321', got {result.get('telegramChatId')!r}"
        )

    @pytest.mark.asyncio
    async def test_patch_me_clears_telegram_chat_id_with_empty_string(self):
        """
        Sending a blank telegram_chat_id strips to empty and the auth.py code
        converts it to None before building the SQL — verified by inspecting
        the values list assembled inside update_me via a capturing mock.
        """
        captured_values: list = []

        # Build a capturing fetchrow that records what values were passed
        saved_row = _FakeRecord({
            "id": "user-tg-123",
            "nome": "Teste TG",
            "email": "tg@example.com",
            "empresa": None,
            "cnpj": None,
            "plano": "profissional",
            "avatar_url": None,
            "criado_em": None,
            "notif_email": True,
            "notif_telegram": False,
            "telegram_chat_id": None,
        })

        async def _capturing_fetchrow(sql, *args):
            captured_values.extend(args)
            return saved_row

        pool = _make_pool()
        pool.fetchrow = _capturing_fetchrow

        current_user = {
            "id": "user-tg-123",
            "nome": "Teste TG",
            "email": "tg@example.com",
            "empresa": None,
            "cnpj": None,
            "plano": "profissional",
            "avatar_url": None,
            "criado_em": None,
            "notif_email": True,
            "notif_telegram": True,
            "telegram_chat_id": "987654321",
        }

        with patch("app.api.auth.get_pool", AsyncMock(return_value=pool)):
            from app.api.auth import update_me, ProfileUpdate
            body = ProfileUpdate(telegram_chat_id="   ")  # blank → None
            result = await update_me(body=body, current_user=current_user)

        # The value passed for telegram_chat_id must be None (not the blank string)
        assert None in captured_values, (
            "Empty/blank telegram_chat_id must be stored as NULL (None). "
            f"Actual values passed to fetchrow: {captured_values}"
        )
        # The API response must reflect the cleared chat ID
        assert result.get("telegramChatId") is None

    @pytest.mark.asyncio
    async def test_patch_me_no_update_when_no_fields(self):
        """
        PATCH /auth/me with no fields returns current user without hitting the DB.
        """
        pool = _make_pool()

        current_user = {
            "id": "user-tg-123",
            "nome": "Teste TG",
            "email": "tg@example.com",
            "empresa": None,
            "cnpj": None,
            "plano": "profissional",
            "avatar_url": None,
            "criado_em": None,
            "notif_email": True,
            "notif_telegram": True,
            "telegram_chat_id": "987654321",
        }

        with patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)):
            from app.api.auth import update_me, ProfileUpdate
            body = ProfileUpdate()  # all None → no-op
            result = await update_me(body=body, current_user=current_user)

        # No DB write when nothing changed
        pool.fetchrow.assert_not_awaited()
        assert result.get("telegramChatId") == "987654321"


# ============================================================================
# _resolve_channels — Telegram channel filtering
# ============================================================================

class TestResolveChannelsTelegram:
    """_resolve_channels must include telegram only when notif_telegram=True."""

    def test_telegram_included_when_flag_true(self):
        from app.services.notification_service import _resolve_channels, CHANNEL_TELEGRAM
        user = _telegram_user()
        result = _resolve_channels(user, [CHANNEL_TELEGRAM])
        assert CHANNEL_TELEGRAM in result, (
            "_resolve_channels must include telegram when notif_telegram=True"
        )

    def test_telegram_excluded_when_flag_false(self):
        from app.services.notification_service import _resolve_channels, CHANNEL_TELEGRAM
        user = _telegram_user(notif_telegram=False)
        result = _resolve_channels(user, [CHANNEL_TELEGRAM])
        assert CHANNEL_TELEGRAM not in result, (
            "_resolve_channels must exclude telegram when notif_telegram=False"
        )

    def test_telegram_excluded_by_default_when_key_absent(self):
        from app.services.notification_service import _resolve_channels, CHANNEL_TELEGRAM
        user = {"id": "u1", "email": "u@example.com"}  # no notif_telegram key
        result = _resolve_channels(user, [CHANNEL_TELEGRAM])
        assert CHANNEL_TELEGRAM not in result, (
            "telegram must default to False (excluded) when key is absent"
        )

    def test_only_telegram_active_among_all_channels(self):
        """A Telegram-only user should have only the telegram channel active."""
        from app.services.notification_service import _resolve_channels, ALL_CHANNELS
        user = _telegram_user(notif_push=False, notif_email=False,
                              notif_whatsapp=False, notif_telegram=True)
        result = _resolve_channels(user, ALL_CHANNELS)
        assert result == ["telegram"], (
            f"Expected only ['telegram'], got {result!r}"
        )


# ============================================================================
# send() — Telegram delivery path with correct chat_id
# ============================================================================

class TestSendTelegramDelivery:
    """send() must call send_telegram with the exact chat_id from the user dict."""

    @pytest.mark.asyncio
    async def test_send_telegram_called_with_correct_chat_id(self):
        """
        When the user has notif_telegram=True and telegram_chat_id='987654321',
        send_telegram must be called with that exact chat_id.
        """
        user = _telegram_user(telegram_chat_id="987654321")
        mock_tg = AsyncMock(return_value=True)

        with patch(f"{TG_MODULE}.send_telegram", mock_tg):
            from app.services.notification_service import send
            result = await send(
                user,
                title="Alerta: licitação atualizada",
                body="O valor estimado foi alterado.",
                channels=["telegram"],
            )

        mock_tg.assert_awaited_once()
        args, _ = mock_tg.call_args
        assert args[0] == "987654321", (
            f"send_telegram must receive chat_id='987654321', got {args[0]!r}"
        )
        assert result.get("telegram") is True

    @pytest.mark.asyncio
    async def test_send_telegram_message_contains_title(self):
        """The message passed to send_telegram must include the notification title."""
        user = _telegram_user()
        mock_tg = AsyncMock(return_value=True)

        with patch(f"{TG_MODULE}.send_telegram", mock_tg):
            from app.services.notification_service import send
            await send(
                user,
                title="Licitação favorita atualizada",
                body="Status mudou de aberto para encerrado.",
                channels=["telegram"],
            )

        args, _ = mock_tg.call_args
        message = args[1]
        assert "Licitação favorita atualizada" in message, (
            f"Title must appear in the Telegram message, got: {message!r}"
        )

    @pytest.mark.asyncio
    async def test_send_telegram_not_called_without_chat_id(self):
        """
        When notif_telegram=True but telegram_chat_id is empty/absent,
        send_telegram must NOT be called and result must be False.
        """
        user = _telegram_user(telegram_chat_id="")
        mock_tg = AsyncMock(return_value=True)

        with patch(f"{TG_MODULE}.send_telegram", mock_tg):
            from app.services.notification_service import send
            result = await send(user, title="T", body="B", channels=["telegram"])

        mock_tg.assert_not_awaited()
        assert result.get("telegram") is False

    @pytest.mark.asyncio
    async def test_send_telegram_not_called_when_flag_false(self):
        """
        When notif_telegram=False, send_telegram must never be invoked,
        even if telegram_chat_id is set.
        """
        user = _telegram_user(notif_telegram=False, telegram_chat_id="987654321")
        mock_tg = AsyncMock(return_value=True)

        with patch(f"{TG_MODULE}.send_telegram", mock_tg):
            from app.services.notification_service import send
            result = await send(user, title="T", body="B", channels=["telegram"])

        mock_tg.assert_not_awaited()
        assert "telegram" not in result

    @pytest.mark.asyncio
    async def test_send_result_false_when_telegram_raises(self):
        """
        If send_telegram raises, the error must be absorbed and result['telegram']
        must be False — no exception propagated to the caller.
        """
        user = _telegram_user()
        mock_tg = AsyncMock(side_effect=ConnectionError("Telegram API timeout"))

        with patch(f"{TG_MODULE}.send_telegram", mock_tg):
            from app.services.notification_service import send
            result = await send(user, title="T", body="B", channels=["telegram"])

        assert result.get("telegram") is False


# ============================================================================
# send_tender_update() — full flow with Telegram-enabled user
# ============================================================================

class TestSendTenderUpdateTelegram:
    """
    send_tender_update() must fire Telegram delivery with the correct chat_id
    when the user has notif_telegram=True and a telegram_chat_id set.
    """

    @pytest.mark.asyncio
    async def test_telegram_channel_fires_on_tender_update(self):
        """
        End-to-end: a user with telegram_chat_id receives a Telegram message
        when a favorited tender changes.
        """
        user   = _telegram_user(telegram_chat_id="555111222")
        tender = _tender()
        changes = {"status": ("aberto", "encerrado")}

        pool    = _make_pool()
        mock_tg = AsyncMock(return_value=True)

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{TG_MODULE}.send_telegram", mock_tg),
        ):
            from app.services.notification_service import send_tender_update
            await send_tender_update(user, tender, changes)

        mock_tg.assert_awaited_once()
        args, _ = mock_tg.call_args
        assert args[0] == "555111222", (
            f"send_telegram must receive chat_id='555111222', got {args[0]!r}"
        )

    @pytest.mark.asyncio
    async def test_telegram_message_contains_tender_object(self):
        """
        The Telegram message body must reference the tender's objeto so the
        user knows which licitação was updated.
        """
        user   = _telegram_user()
        tender = _tender(objeto="Aquisição de equipamentos de TI")
        changes = {"valor": ("400000", "500000")}

        pool    = _make_pool()
        mock_tg = AsyncMock(return_value=True)

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{TG_MODULE}.send_telegram", mock_tg),
        ):
            from app.services.notification_service import send_tender_update
            await send_tender_update(user, tender, changes)

        args, _ = mock_tg.call_args
        message = args[1]
        assert "Aquisição de equipamentos de TI" in message, (
            f"Tender objeto must appear in the Telegram message, got: {message!r}"
        )

    @pytest.mark.asyncio
    async def test_telegram_not_called_when_notif_telegram_false(self):
        """
        When notif_telegram=False, send_tender_update must not call send_telegram
        even if telegram_chat_id is populated.
        """
        user   = _telegram_user(notif_telegram=False, telegram_chat_id="555111222")
        tender = _tender()
        changes = {"status": ("aberto", "encerrado")}

        pool    = _make_pool()
        mock_tg = AsyncMock(return_value=True)

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{TG_MODULE}.send_telegram", mock_tg),
        ):
            from app.services.notification_service import send_tender_update
            await send_tender_update(user, tender, changes)

        mock_tg.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_tender_update_alert_persisted_regardless_of_telegram(self):
        """
        The DB alert must be persisted even when the Telegram channel fires,
        and send_tender_update must return True indicating successful persistence.
        """
        user   = _telegram_user()
        tender = _tender()
        changes = {"prazo": ("2026-08-01", "2026-08-15")}

        pool    = _make_pool()
        mock_tg = AsyncMock(return_value=True)

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{TG_MODULE}.send_telegram", mock_tg),
        ):
            from app.services.notification_service import send_tender_update
            persisted = await send_tender_update(user, tender, changes)

        assert persisted is True, (
            "send_tender_update must return True when the DB INSERT succeeds"
        )
        # send_tender_update uses fetchval (INSERT…RETURNING id), not execute
        pool.fetchval.assert_awaited()

    @pytest.mark.asyncio
    async def test_telegram_chat_id_propagated_from_user_dict(self):
        """
        Regression: confirm the chat_id read from user['telegram_chat_id'] (not
        some other field) is what reaches send_telegram.
        """
        # Deliberately set a non-obvious chat_id to catch any field-name confusion
        user   = _telegram_user(telegram_chat_id="UNIQUE-CHAT-ID-XYZ")
        tender = _tender()
        changes = {"objeto": ("Descrição antiga", "Descrição nova")}

        pool    = _make_pool()
        mock_tg = AsyncMock(return_value=True)

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{TG_MODULE}.send_telegram", mock_tg),
        ):
            from app.services.notification_service import send_tender_update
            await send_tender_update(user, tender, changes)

        args, _ = mock_tg.call_args
        assert args[0] == "UNIQUE-CHAT-ID-XYZ", (
            f"chat_id must come from user['telegram_chat_id']; got {args[0]!r}"
        )
