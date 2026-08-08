"""
test_notification_service.py

Unit tests for notification_service.py.

Verifica que:
- send() despacha para push_sender e email_sender com os argumentos corretos
  quando as flags notif_push / notif_email estão ativas.
- send() NÃO chama nenhum sender quando todas as flags estão desativadas.
- send_monitor_match() chama send() com título, corpo e metadata corretos.
- send_document_expiration() chama send() com título e tipo corretos
  para certidões vencidas, que vencem hoje e que vencem no futuro.
- Canais WhatsApp / Telegram só são chamados quando o campo de contato
  do usuário existe; retornam False quando não existe.
- Erros internos de sender são absorvidos: send() retorna False para
  aquele canal sem propagar exceção.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

# Módulo que será testado (importado dentro dos testes para evitar
# side-effects de importação antecipada com deps não disponíveis)
NOTIF_MODULE   = "app.services.notification_service"
PUSH_MODULE    = "app.services.senders.push_sender"
EMAIL_MODULE   = "app.services.senders.email_sender"
WA_MODULE      = "app.services.senders.whatsapp_sender"
TG_MODULE      = "app.services.senders.telegram_sender"
DB_SESSION_MOD = "app.db.session"


# ── helpers ───────────────────────────────────────────────────────────────────

def _user(**overrides) -> dict:
    """Cria um dict de usuário com preferências padrão."""
    base = {
        "id": 1,
        "email": "user@example.com",
        "notif_push": True,
        "notif_email": True,
        "notif_whatsapp": False,
        "notif_telegram": False,
    }
    base.update(overrides)
    return base


def _monitor(**overrides) -> dict:
    base = {"id": 10, "nome": "Monitor Teste"}
    base.update(overrides)
    return base


def _tender(**overrides) -> dict:
    base = {
        "id": "LICIT-001",
        "objeto": "Aquisição de material de escritório",
        "orgao": "Prefeitura SP",
        "uf": "SP",
        "valorEstimado": 150000.0,
        "source": "pncp",
    }
    base.update(overrides)
    return base


def _certidao(**overrides) -> dict:
    base = {"id": 5, "nome": "Certidão FGTS"}
    base.update(overrides)
    return base


# ── Pool mock simples (sem acesso a DB real) ──────────────────────────────────

def _make_pool() -> MagicMock:
    pool = MagicMock()
    pool.execute  = AsyncMock(return_value="OK")
    pool.fetchval = AsyncMock(return_value=None)
    pool.acquire  = MagicMock()

    # Suporte a `async with pool.acquire() as conn`
    conn = MagicMock()
    conn.execute = AsyncMock(return_value="OK")
    conn.transaction = MagicMock()

    # transaction context manager
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__  = AsyncMock(return_value=False)
    conn.transaction.return_value = tx

    # acquire context manager
    acq = MagicMock()
    acq.__aenter__ = AsyncMock(return_value=conn)
    acq.__aexit__  = AsyncMock(return_value=False)
    pool.acquire.return_value = acq

    return pool


# ============================================================================
# send() — roteamento por canal
# ============================================================================

class TestSendRouting:
    """send() deve despachar para o sender correto conforme os canais ativos."""

    @pytest.mark.asyncio
    async def test_push_channel_called_when_notif_push_true(self):
        """Quando notif_push=True, send_push deve ser chamado com user_id, title, body."""
        user = _user(notif_push=True, notif_email=False)
        mock_push = AsyncMock(return_value=True)

        with patch(f"{PUSH_MODULE}.send_push", mock_push):
            from app.services.notification_service import send
            result = await send(
                user, title="Título", body="Corpo",
                channels=["push"], tipo="info",
            )

        mock_push.assert_awaited_once()
        args, kwargs = mock_push.call_args
        assert args[0] == str(user["id"])   # user_id
        assert args[1] == "Título"           # title
        assert args[2] == "Corpo"            # body
        assert result.get("push") is True

    @pytest.mark.asyncio
    async def test_email_channel_called_when_notif_email_true(self):
        """Quando notif_email=True, send_email deve ser chamado com to, subject, body."""
        user = _user(notif_push=False, notif_email=True)
        mock_email = AsyncMock(return_value=True)

        with patch(f"{EMAIL_MODULE}.send_email", mock_email):
            from app.services.notification_service import send
            result = await send(
                user, title="Assunto", body="Mensagem",
                channels=["email"],
                cta_url="https://example.com", cta_label="Ver",
            )

        mock_email.assert_awaited_once()
        _, kwargs = mock_email.call_args
        assert kwargs["to"] == user["email"]
        assert kwargs["subject"] == "Assunto"
        assert kwargs["body_text"] == "Mensagem"
        assert kwargs["cta_url"] == "https://example.com"
        assert kwargs["cta_label"] == "Ver"
        assert result.get("email") is True

    @pytest.mark.asyncio
    async def test_both_push_and_email_called(self):
        """Com notif_push=True e notif_email=True, ambos os senders são chamados."""
        user = _user(notif_push=True, notif_email=True)
        mock_push  = AsyncMock(return_value=True)
        mock_email = AsyncMock(return_value=True)

        with (
            patch(f"{PUSH_MODULE}.send_push",   mock_push),
            patch(f"{EMAIL_MODULE}.send_email",  mock_email),
        ):
            from app.services.notification_service import send
            result = await send(user, title="T", body="B", channels=["push", "email"])

        mock_push.assert_awaited_once()
        mock_email.assert_awaited_once()
        assert result.get("push")  is True
        assert result.get("email") is True

    @pytest.mark.asyncio
    async def test_no_sender_called_when_all_flags_false(self):
        """Quando todas as flags notif_* são False, nenhum sender é chamado."""
        user = _user(notif_push=False, notif_email=False,
                     notif_whatsapp=False, notif_telegram=False)
        mock_push  = AsyncMock(return_value=True)
        mock_email = AsyncMock(return_value=True)

        with (
            patch(f"{PUSH_MODULE}.send_push",   mock_push),
            patch(f"{EMAIL_MODULE}.send_email",  mock_email),
        ):
            from app.services.notification_service import send
            result = await send(user, title="T", body="B",
                                channels=["push", "email", "whatsapp", "telegram"])

        mock_push.assert_not_awaited()
        mock_email.assert_not_awaited()
        assert result == {}

    @pytest.mark.asyncio
    async def test_result_keyed_by_channel(self):
        """O dict retornado deve ter uma chave por canal ativo."""
        user = _user(notif_push=True, notif_email=True)
        with (
            patch(f"{PUSH_MODULE}.send_push",  AsyncMock(return_value=True)),
            patch(f"{EMAIL_MODULE}.send_email", AsyncMock(return_value=True)),
        ):
            from app.services.notification_service import send
            result = await send(user, title="T", body="B", channels=["push", "email"])

        assert set(result.keys()) == {"push", "email"}


# ============================================================================
# send() — preferências de usuário (_resolve_channels)
# ============================================================================

class TestResolveChannels:
    """_resolve_channels filtra os canais conforme as flags do usuário."""

    @pytest.mark.asyncio
    async def test_push_skipped_when_notif_push_false(self):
        """notif_push=False → push_sender nunca é chamado."""
        user = _user(notif_push=False, notif_email=True)
        mock_push  = AsyncMock(return_value=True)
        mock_email = AsyncMock(return_value=True)

        with (
            patch(f"{PUSH_MODULE}.send_push",   mock_push),
            patch(f"{EMAIL_MODULE}.send_email",  mock_email),
        ):
            from app.services.notification_service import send
            result = await send(user, title="T", body="B", channels=["push", "email"])

        mock_push.assert_not_awaited()
        mock_email.assert_awaited_once()
        assert "push" not in result
        assert result.get("email") is True

    @pytest.mark.asyncio
    async def test_email_skipped_when_notif_email_false(self):
        """notif_email=False → email_sender nunca é chamado."""
        user = _user(notif_push=True, notif_email=False)
        mock_push  = AsyncMock(return_value=True)
        mock_email = AsyncMock(return_value=True)

        with (
            patch(f"{PUSH_MODULE}.send_push",   mock_push),
            patch(f"{EMAIL_MODULE}.send_email",  mock_email),
        ):
            from app.services.notification_service import send
            result = await send(user, title="T", body="B", channels=["push", "email"])

        mock_push.assert_awaited_once()
        mock_email.assert_not_awaited()
        assert "email" not in result
        assert result.get("push") is True

    @pytest.mark.asyncio
    async def test_defaults_true_when_notif_keys_absent(self):
        """Usuário sem chaves notif_* deve ter push e email ativos por padrão."""
        user = {"id": 99, "email": "anon@example.com"}  # sem flags
        mock_push  = AsyncMock(return_value=True)
        mock_email = AsyncMock(return_value=True)

        with (
            patch(f"{PUSH_MODULE}.send_push",   mock_push),
            patch(f"{EMAIL_MODULE}.send_email",  mock_email),
        ):
            from app.services.notification_service import send
            result = await send(user, title="T", body="B", channels=["push", "email"])

        mock_push.assert_awaited_once()
        mock_email.assert_awaited_once()
        assert result.get("push")  is True
        assert result.get("email") is True


# ============================================================================
# send() — tratamento de erros de sender
# ============================================================================

class TestSendErrorHandling:
    """Erros levantados por senders devem ser absorvidos."""

    @pytest.mark.asyncio
    async def test_push_exception_absorbed_returns_false(self):
        """send_push levantando exceção → result['push'] = False, sem reraise."""
        user = _user(notif_push=True, notif_email=False)
        mock_push = AsyncMock(side_effect=RuntimeError("SMTP timeout"))

        with patch(f"{PUSH_MODULE}.send_push", mock_push):
            from app.services.notification_service import send
            result = await send(user, title="T", body="B", channels=["push"])

        assert result.get("push") is False

    @pytest.mark.asyncio
    async def test_email_exception_absorbed_returns_false(self):
        """send_email levantando exceção → result['email'] = False, sem reraise."""
        user = _user(notif_push=False, notif_email=True)
        mock_email = AsyncMock(side_effect=ConnectionError("SMTP down"))

        with patch(f"{EMAIL_MODULE}.send_email", mock_email):
            from app.services.notification_service import send
            result = await send(user, title="T", body="B", channels=["email"])

        assert result.get("email") is False

    @pytest.mark.asyncio
    async def test_one_channel_failure_does_not_prevent_other(self):
        """Falha em push não impede envio de email e vice-versa."""
        user = _user(notif_push=True, notif_email=True)
        mock_push  = AsyncMock(side_effect=Exception("push error"))
        mock_email = AsyncMock(return_value=True)

        with (
            patch(f"{PUSH_MODULE}.send_push",   mock_push),
            patch(f"{EMAIL_MODULE}.send_email",  mock_email),
        ):
            from app.services.notification_service import send
            result = await send(user, title="T", body="B", channels=["push", "email"])

        assert result.get("push")  is False
        assert result.get("email") is True


# ============================================================================
# send() — canal WhatsApp
# ============================================================================

class TestWhatsappChannel:
    """WhatsApp só é chamado quando notif_whatsapp=True e phone está presente."""

    @pytest.mark.asyncio
    async def test_whatsapp_called_with_phone(self):
        """Com notif_whatsapp=True e phone presente, send_whatsapp é chamado."""
        user = _user(notif_push=False, notif_email=False,
                     notif_whatsapp=True, phone="+5511999999999")
        mock_wa = AsyncMock(return_value=True)

        with patch(f"{WA_MODULE}.send_whatsapp", mock_wa):
            from app.services.notification_service import send
            result = await send(user, title="Título", body="Corpo", channels=["whatsapp"])

        mock_wa.assert_awaited_once()
        args, _ = mock_wa.call_args
        assert args[0] == "+5511999999999"
        assert "Título" in args[1]
        assert result.get("whatsapp") is True

    @pytest.mark.asyncio
    async def test_whatsapp_returns_false_without_phone(self):
        """Com notif_whatsapp=True mas sem phone, retorna False sem chamar sender."""
        user = _user(notif_push=False, notif_email=False, notif_whatsapp=True)
        mock_wa = AsyncMock(return_value=True)

        with patch(f"{WA_MODULE}.send_whatsapp", mock_wa):
            from app.services.notification_service import send
            result = await send(user, title="T", body="B", channels=["whatsapp"])

        mock_wa.assert_not_awaited()
        assert result.get("whatsapp") is False


# ============================================================================
# send() — canal Telegram
# ============================================================================

class TestTelegramChannel:
    """Telegram só é chamado quando notif_telegram=True e chat_id está presente."""

    @pytest.mark.asyncio
    async def test_telegram_called_with_chat_id(self):
        """Com notif_telegram=True e telegram_chat_id presente, sender é chamado."""
        user = _user(notif_push=False, notif_email=False,
                     notif_telegram=True, telegram_chat_id="987654321")
        mock_tg = AsyncMock(return_value=True)

        with patch(f"{TG_MODULE}.send_telegram", mock_tg):
            from app.services.notification_service import send
            result = await send(user, title="Alert", body="Texto", channels=["telegram"])

        mock_tg.assert_awaited_once()
        args, _ = mock_tg.call_args
        assert args[0] == "987654321"
        assert "Alert" in args[1]
        assert result.get("telegram") is True

    @pytest.mark.asyncio
    async def test_telegram_returns_false_without_chat_id(self):
        """Com notif_telegram=True mas sem chat_id, retorna False sem chamar sender."""
        user = _user(notif_push=False, notif_email=False, notif_telegram=True)
        mock_tg = AsyncMock(return_value=True)

        with patch(f"{TG_MODULE}.send_telegram", mock_tg):
            from app.services.notification_service import send
            result = await send(user, title="T", body="B", channels=["telegram"])

        mock_tg.assert_not_awaited()
        assert result.get("telegram") is False


# ============================================================================
# send_monitor_match()
# ============================================================================

class TestSendMonitorMatch:
    """send_monitor_match() deve formatar a mensagem e chamar send() corretamente."""

    @pytest.mark.asyncio
    async def test_calls_send_with_correct_title_and_body(self):
        """O título deve mencionar o nome do monitor; o corpo menciona objeto e órgão."""
        user    = _user()
        monitor = _monitor(id=10, nome="Monitor SP")
        tender  = _tender(objeto="Construção de escola", orgao="Pref SP", uf="SP",
                          valorEstimado=200000.0)

        pool = _make_pool()
        captured: list[dict] = []

        async def _fake_send(u, title, body, **kwargs):
            captured.append({"title": title, "body": body, "kwargs": kwargs})
            return {"push": True, "email": True}

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_MODULE}.send", side_effect=_fake_send),
        ):
            from app.services.notification_service import send_monitor_match
            await send_monitor_match(user, monitor, tender)

        assert len(captured) == 1
        c = captured[0]
        assert "Monitor SP" in c["title"]
        assert "Construção de escola" in c["body"]
        assert "Pref SP" in c["body"]

    @pytest.mark.asyncio
    async def test_metadata_contains_monitor_and_tender_ids(self):
        """metadata deve incluir monitor_id e tender_id."""
        user    = _user()
        monitor = _monitor(id=42, nome="Monitor X")
        tender  = _tender(id="TID-999")

        pool = _make_pool()
        captured_kwargs: list[dict] = []

        async def _fake_send(u, title, body, **kwargs):
            captured_kwargs.append(kwargs)
            return {}

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_MODULE}.send", side_effect=_fake_send),
        ):
            from app.services.notification_service import send_monitor_match
            await send_monitor_match(user, monitor, tender)

        assert captured_kwargs, "send() deve ter sido chamado"
        meta = captured_kwargs[0].get("metadata", {})
        assert str(meta.get("monitor_id")) == "42"
        assert str(meta.get("tender_id")) == "TID-999"

    @pytest.mark.asyncio
    async def test_tipo_is_match(self):
        """tipo deve ser 'match' para alertas de monitor."""
        user    = _user()
        monitor = _monitor()
        tender  = _tender()

        pool = _make_pool()
        captured_kwargs: list[dict] = []

        async def _fake_send(u, title, body, **kwargs):
            captured_kwargs.append(kwargs)
            return {}

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_MODULE}.send", side_effect=_fake_send),
        ):
            from app.services.notification_service import send_monitor_match
            await send_monitor_match(user, monitor, tender)

        assert captured_kwargs[0].get("tipo") == "match"

    @pytest.mark.asyncio
    async def test_valor_nao_informado_when_missing(self):
        """Quando o tender não tem valor, o corpo deve conter 'Não informado'."""
        user    = _user()
        monitor = _monitor()
        tender  = _tender(valorEstimado=None, valor_estimado=None)

        pool = _make_pool()
        captured: list[dict] = []

        async def _fake_send(u, title, body, **kwargs):
            captured.append({"body": body})
            return {}

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_MODULE}.send", side_effect=_fake_send),
        ):
            from app.services.notification_service import send_monitor_match
            await send_monitor_match(user, monitor, tender)

        assert "Não informado" in captured[0]["body"]

    @pytest.mark.asyncio
    async def test_uses_background_tasks_when_provided(self):
        """Com background_tasks fornecido, add_task deve ser chamado (não await send)."""
        user    = _user()
        monitor = _monitor()
        tender  = _tender()

        pool = _make_pool()
        mock_send = AsyncMock(return_value={})
        bg = MagicMock()
        bg.add_task = MagicMock()

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_MODULE}.send", mock_send),
        ):
            from app.services.notification_service import send_monitor_match
            await send_monitor_match(user, monitor, tender, background_tasks=bg)

        bg.add_task.assert_called_once()
        mock_send.assert_not_awaited()


# ============================================================================
# send_document_expiration()
# ============================================================================

class TestSendDocumentExpiration:
    """send_document_expiration() — título e tipo corretos para cada vencimento."""

    @pytest.mark.asyncio
    async def test_tipo_error_when_expired(self):
        """Certidão vencida → tipo='error' e título contém 'VENCIDA'."""
        user     = _user()
        certidao = _certidao(nome="Certidão FGTS")
        pool = _make_pool()
        captured: list[dict] = []

        async def _fake_send(u, title, body, **kwargs):
            captured.append({"title": title, "tipo": kwargs.get("tipo")})
            return {}

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_MODULE}.send", side_effect=_fake_send),
        ):
            from app.services.notification_service import send_document_expiration
            await send_document_expiration(user, certidao, dias_restantes=-3)

        assert captured, "send() deve ter sido chamado"
        assert captured[0]["tipo"] == "error"
        assert "VENCIDA" in captured[0]["title"]

    @pytest.mark.asyncio
    async def test_tipo_error_when_expires_today(self):
        """Certidão vence hoje → tipo='error' e título contém 'HOJE'."""
        user     = _user()
        certidao = _certidao(nome="Certidão Municipal")
        pool = _make_pool()
        captured: list[dict] = []

        async def _fake_send(u, title, body, **kwargs):
            captured.append({"title": title, "tipo": kwargs.get("tipo")})
            return {}

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_MODULE}.send", side_effect=_fake_send),
        ):
            from app.services.notification_service import send_document_expiration
            await send_document_expiration(user, certidao, dias_restantes=0)

        assert captured[0]["tipo"] == "error"
        assert "HOJE" in captured[0]["title"]

    @pytest.mark.asyncio
    async def test_tipo_warning_when_expires_soon(self):
        """Certidão vence em N dias → tipo='warning' e título contém dias restantes."""
        user     = _user()
        certidao = _certidao(nome="Certidão Receita")
        pool = _make_pool()
        captured: list[dict] = []

        async def _fake_send(u, title, body, **kwargs):
            captured.append({"title": title, "tipo": kwargs.get("tipo")})
            return {}

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_MODULE}.send", side_effect=_fake_send),
        ):
            from app.services.notification_service import send_document_expiration
            await send_document_expiration(user, certidao, dias_restantes=7)

        assert captured[0]["tipo"] == "warning"
        assert "7" in captured[0]["title"]

    @pytest.mark.asyncio
    async def test_cert_name_in_body(self):
        """O nome da certidão deve aparecer no corpo da mensagem."""
        user     = _user()
        certidao = _certidao(nome="CND Federal Especial")
        pool = _make_pool()
        captured: list[dict] = []

        async def _fake_send(u, title, body, **kwargs):
            captured.append({"body": body})
            return {}

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_MODULE}.send", side_effect=_fake_send),
        ):
            from app.services.notification_service import send_document_expiration
            await send_document_expiration(user, certidao, dias_restantes=14)

        assert "CND Federal Especial" in captured[0]["body"]

    @pytest.mark.asyncio
    async def test_background_tasks_used_when_provided(self):
        """Com background_tasks, deve usar add_task em vez de awaitar send."""
        user     = _user()
        certidao = _certidao()
        pool = _make_pool()
        mock_send = AsyncMock(return_value={})
        bg = MagicMock()
        bg.add_task = MagicMock()

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_MODULE}.send", mock_send),
        ):
            from app.services.notification_service import send_document_expiration
            await send_document_expiration(user, certidao, dias_restantes=5, background_tasks=bg)

        bg.add_task.assert_called_once()
        mock_send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_send_when_all_notif_flags_false(self):
        """Usuário sem nenhuma flag de notificação ativa → send não envia nada."""
        user     = _user(notif_push=False, notif_email=False,
                         notif_whatsapp=False, notif_telegram=False)
        certidao = _certidao()
        pool = _make_pool()
        mock_push  = AsyncMock(return_value=True)
        mock_email = AsyncMock(return_value=True)

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{PUSH_MODULE}.send_push",   mock_push),
            patch(f"{EMAIL_MODULE}.send_email",  mock_email),
        ):
            from app.services.notification_service import send_document_expiration
            await send_document_expiration(user, certidao, dias_restantes=10)

        mock_push.assert_not_awaited()
        mock_email.assert_not_awaited()


# ============================================================================
# send_tender_update()
# ============================================================================

class TestSendTenderUpdate:
    """send_tender_update() deve formatar mudanças e chamar send() corretamente."""

    @pytest.mark.asyncio
    async def test_title_contains_objeto(self):
        """O título deve mencionar o objeto da licitação."""
        user   = _user()
        tender = {"id": "T1", "objeto": "Reforma do ginásio municipal"}
        changes = {"status": ("aberto", "encerrado")}

        pool = _make_pool()
        captured: list[dict] = []

        async def _fake_send(u, title, body, **kwargs):
            captured.append({"title": title, "body": body})
            return {}

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_MODULE}.send", side_effect=_fake_send),
        ):
            from app.services.notification_service import send_tender_update
            await send_tender_update(user, tender, changes)

        assert captured, "send() deve ter sido chamado"
        assert "Reforma do ginásio municipal" in captured[0]["title"]

    @pytest.mark.asyncio
    async def test_body_contains_all_changed_fields(self):
        """O corpo deve listar todos os campos alterados com valores antigo→novo."""
        user   = _user()
        tender = {"id": "T2", "objeto": "Aquisição de veículos"}
        changes = {
            "status":    ("aberto",   "suspenso"),
            "valor":     ("100000",   "150000"),
        }

        pool = _make_pool()
        captured: list[dict] = []

        async def _fake_send(u, title, body, **kwargs):
            captured.append({"body": body})
            return {}

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_MODULE}.send", side_effect=_fake_send),
        ):
            from app.services.notification_service import send_tender_update
            await send_tender_update(user, tender, changes)

        body = captured[0]["body"]
        assert "status" in body
        assert "aberto" in body and "suspenso" in body
        assert "valor" in body
        assert "100000" in body and "150000" in body

    @pytest.mark.asyncio
    async def test_metadata_contains_tender_id_and_changes(self):
        """metadata deve incluir tender_id e o dict de mudanças serializado."""
        user   = _user()
        tender = {"id": "TENDER-42", "objeto": "Serviços de TI"}
        changes = {"modalidade": ("pregão", "concorrência")}

        pool = _make_pool()
        captured_kw: list[dict] = []

        async def _fake_send(u, title, body, **kwargs):
            captured_kw.append(kwargs)
            return {}

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_MODULE}.send", side_effect=_fake_send),
        ):
            from app.services.notification_service import send_tender_update
            await send_tender_update(user, tender, changes)

        meta = captured_kw[0].get("metadata", {})
        assert str(meta.get("tender_id")) == "TENDER-42"
        assert "changes" in meta
        assert "modalidade" in meta["changes"]
        assert meta["changes"]["modalidade"]["from"] == "pregão"
        assert meta["changes"]["modalidade"]["to"] == "concorrência"

    @pytest.mark.asyncio
    async def test_tipo_is_update(self):
        """tipo deve ser 'update' para alertas de atualização de licitação."""
        user   = _user()
        tender = {"id": "T3", "objeto": "Obras de saneamento"}
        changes = {"data_abertura": ("2024-01-01", "2024-02-01")}

        pool = _make_pool()
        captured_kw: list[dict] = []

        async def _fake_send(u, title, body, **kwargs):
            captured_kw.append(kwargs)
            return {}

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_MODULE}.send", side_effect=_fake_send),
        ):
            from app.services.notification_service import send_tender_update
            await send_tender_update(user, tender, changes)

        assert captured_kw[0].get("tipo") == "update"

    @pytest.mark.asyncio
    async def test_push_and_email_dispatched_based_on_flags(self):
        """Flags notif_push/notif_email controlam quais senders são chamados."""
        user   = _user(notif_push=True, notif_email=True)
        tender = {"id": "T4", "objeto": "Material de limpeza"}
        changes = {"status": ("aberto", "homologado")}

        pool = _make_pool()
        mock_push  = AsyncMock(return_value=True)
        mock_email = AsyncMock(return_value=True)

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{PUSH_MODULE}.send_push",   mock_push),
            patch(f"{EMAIL_MODULE}.send_email",  mock_email),
        ):
            from app.services.notification_service import send_tender_update
            await send_tender_update(user, tender, changes)

        mock_push.assert_awaited_once()
        mock_email.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_sender_called_when_all_flags_false(self):
        """Com todas as flags False, nenhum sender é acionado."""
        user   = _user(notif_push=False, notif_email=False,
                       notif_whatsapp=False, notif_telegram=False)
        tender = {"id": "T5", "objeto": "Serviços de limpeza"}
        changes = {"status": ("aberto", "cancelado")}

        pool = _make_pool()
        mock_push  = AsyncMock(return_value=True)
        mock_email = AsyncMock(return_value=True)

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{PUSH_MODULE}.send_push",   mock_push),
            patch(f"{EMAIL_MODULE}.send_email",  mock_email),
        ):
            from app.services.notification_service import send_tender_update
            await send_tender_update(user, tender, changes)

        mock_push.assert_not_awaited()
        mock_email.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_background_tasks_used_when_provided(self):
        """Com background_tasks, deve usar add_task em vez de awaitar send."""
        user   = _user()
        tender = {"id": "T6", "objeto": "Obras elétrica"}
        changes = {"valor": ("50000", "60000")}

        pool = _make_pool()
        mock_send = AsyncMock(return_value={})
        bg = MagicMock()
        bg.add_task = MagicMock()

        with (
            patch(f"{DB_SESSION_MOD}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_MODULE}.send", mock_send),
        ):
            from app.services.notification_service import send_tender_update
            await send_tender_update(user, tender, changes, background_tasks=bg)

        bg.add_task.assert_called_once()
        mock_send.assert_not_awaited()


# ============================================================================
# Sender contract tests — email_sender
# Lazy imports inside send_email mean we patch at the source module.
# ============================================================================

# Paths used by email_sender's lazy imports
_EMAIL_SETTINGS_MOD = "app.core.config"
_AIOSMTP_MOD        = "aiosmtplib"

class TestEmailSenderContract:
    """Testa o comportamento do email_sender na boundary com o transporte SMTP."""

    @pytest.mark.asyncio
    async def test_returns_true_when_smtp_not_configured(self):
        """Sem SMTP configurado (dev mode), send_email deve retornar True sem enviar."""
        mock_settings = MagicMock()
        mock_settings.smtp_user     = ""
        mock_settings.smtp_password = ""

        with patch(f"{_EMAIL_SETTINGS_MOD}.get_settings", return_value=mock_settings):
            from app.services.senders.email_sender import send_email
            result = await send_email(
                to="user@example.com",
                subject="Teste",
                body_text="Corpo do email",
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_calls_aiosmtplib_send_with_correct_params(self):
        """Com SMTP configurado, aiosmtplib.send deve ser chamado com hostname e credenciais."""
        mock_settings = MagicMock()
        mock_settings.smtp_user      = "noreply@licitaim.com"
        mock_settings.smtp_password  = "secret"
        mock_settings.smtp_host      = "smtp.example.com"
        mock_settings.smtp_port      = 587
        mock_settings.smtp_from      = "noreply@licitaim.com"
        mock_settings.smtp_from_name = "LicitAIM"

        mock_aiosmtp_send = AsyncMock(return_value=None)

        with (
            patch(f"{_EMAIL_SETTINGS_MOD}.get_settings", return_value=mock_settings),
            patch(f"{_AIOSMTP_MOD}.send", mock_aiosmtp_send),
        ):
            from app.services.senders.email_sender import send_email
            result = await send_email(
                to="dest@example.com",
                subject="Alerta de licitação",
                body_text="Detalhes aqui",
                cta_url="https://licitaim.com.br",
                cta_label="Ver",
            )

        assert result is True
        mock_aiosmtp_send.assert_awaited_once()
        _, kwargs = mock_aiosmtp_send.call_args
        assert kwargs["hostname"] == "smtp.example.com"
        assert kwargs["port"] == 587
        assert kwargs["username"] == "noreply@licitaim.com"

    @pytest.mark.asyncio
    async def test_returns_false_when_smtp_raises(self):
        """Se aiosmtplib.send levantar exceção, send_email deve retornar False sem reraise."""
        mock_settings = MagicMock()
        mock_settings.smtp_user      = "noreply@licitaim.com"
        mock_settings.smtp_password  = "secret"
        mock_settings.smtp_host      = "smtp.example.com"
        mock_settings.smtp_port      = 587
        mock_settings.smtp_from      = "noreply@licitaim.com"
        mock_settings.smtp_from_name = "LicitAIM"

        with (
            patch(f"{_EMAIL_SETTINGS_MOD}.get_settings", return_value=mock_settings),
            patch(f"{_AIOSMTP_MOD}.send", AsyncMock(side_effect=ConnectionError("SMTP down"))),
        ):
            from app.services.senders.email_sender import send_email
            result = await send_email(
                to="dest@example.com",
                subject="Teste falha",
                body_text="Corpo",
            )

        assert result is False

    def test_html_template_includes_cta_when_provided(self):
        """O HTML gerado deve incluir o CTA link quando cta_url e cta_label são passados."""
        from app.services.senders.email_sender import _html_template
        html = _html_template(
            "Título", "Corpo", "https://licitaim.com.br/licitacoes", "Ver licitação"
        )

        assert "https://licitaim.com.br/licitacoes" in html
        assert "Ver licitação" in html

    def test_html_template_omits_cta_when_not_provided(self):
        """Sem CTA, o HTML não deve conter botões extras."""
        from app.services.senders.email_sender import _html_template
        html = _html_template("Título", "Corpo")

        # nenhum href de CTA deve aparecer
        assert "Ver licitação" not in html


# ============================================================================
# Sender contract tests — push_sender
# Lazy imports inside send_push mean we patch at the source modules.
# ============================================================================

# Paths used by push_sender's lazy imports
_PUSH_POOL_MOD = "app.db.session"
_PUSH_WS_MOD   = "app.services.websocket_manager"

class TestPushSenderContract:
    """Testa o comportamento do push_sender na boundary com o banco e WebSocket."""

    @pytest.mark.asyncio
    async def test_inserts_notification_and_returns_true(self):
        """send_push deve inserir na tabela notifications e retornar True."""
        import datetime
        mock_row = {"id": 101, "criado_em": datetime.datetime(2026, 1, 1, 12, 0)}
        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(return_value=mock_row)

        mock_ws = MagicMock()
        mock_ws.send_personal = AsyncMock(return_value=True)

        with (
            patch(f"{_PUSH_POOL_MOD}.get_pool", AsyncMock(return_value=mock_pool)),
            patch(f"{_PUSH_WS_MOD}.get_ws_manager", return_value=mock_ws),
        ):
            from app.services.senders.push_sender import send_push
            result = await send_push(
                user_id="42",
                title="Novo match",
                body="Monitor ativado",
                tipo="match",
                metadata={"monitor_id": 1},
            )

        assert result is True
        mock_pool.fetchrow.assert_awaited_once()
        sql_call = mock_pool.fetchrow.call_args[0][0]
        assert "notifications" in sql_call.lower()

    @pytest.mark.asyncio
    async def test_returns_false_when_db_insert_fails(self):
        """Se o INSERT falhar, send_push deve retornar False sem reraise."""
        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(side_effect=Exception("DB connection lost"))

        with patch(f"{_PUSH_POOL_MOD}.get_pool", AsyncMock(return_value=mock_pool)):
            from app.services.senders.push_sender import send_push
            result = await send_push(
                user_id="99",
                title="Alerta",
                body="Corpo",
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_ws_delivery_attempted_after_db_insert(self):
        """Após INSERT bem-sucedido, send_personal do WS manager deve ser chamado."""
        import datetime
        mock_row = {"id": 200, "criado_em": datetime.datetime(2026, 1, 1)}
        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(return_value=mock_row)

        mock_ws = MagicMock()
        mock_ws.send_personal = AsyncMock(return_value=False)  # offline, não entregue

        with (
            patch(f"{_PUSH_POOL_MOD}.get_pool", AsyncMock(return_value=mock_pool)),
            patch(f"{_PUSH_WS_MOD}.get_ws_manager", return_value=mock_ws),
        ):
            from app.services.senders.push_sender import send_push
            result = await send_push(user_id="7", title="T", body="B")

        # DB persistiu → True; WS não entregou (offline) mas isso não é falha
        assert result is True
        # WS delivery was attempted with the correct user_id
        mock_ws.send_personal.assert_awaited_once()
        ws_args = mock_ws.send_personal.call_args[0]
        assert ws_args[0] == "7"                          # user_id correto
        assert ws_args[1]["type"] == "notification"       # payload estruturado
        assert ws_args[1]["title"] == "T"
        assert ws_args[1]["id"] == 200                    # id da row inserida
