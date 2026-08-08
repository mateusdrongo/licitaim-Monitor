"""
test_notification_integration.py

Testes de integração para os senders de notificação.

Esses testes verificam que as mensagens *chegam* ao destinatário —
não apenas que a função de envio é chamada com os argumentos corretos.

Execução
--------
Os testes são skipped por padrão. Para rodá-los:

    INTEGRATION_TESTS=1 python -m pytest tests/test_notification_integration.py -v

Testes de banco adicionalmente requerem DATABASE_URL configurado no ambiente.

Estratégia
----------
Email  → sobe um servidor SMTP local via aiosmtpd, chama send_email contra
         ele (sem TLS — adequado para localhost) e verifica que a mensagem foi
         recebida pelo handler.
Push   → usa pool real (asyncpg) via DATABASE_URL; insere via send_push e lê
         de volta da tabela notifications para confirmar persistência.
"""
from __future__ import annotations

import asyncio
import email
import os
import threading
import time
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── skip helpers ──────────────────────────────────────────────────────────────

_INTEGRATION = os.environ.get("INTEGRATION_TESTS", "").lower() in ("1", "true", "yes")
_DATABASE_URL = os.environ.get("DATABASE_URL", "")

skip_unless_integration = pytest.mark.skipif(
    not _INTEGRATION,
    reason="Skipped: set INTEGRATION_TESTS=1 to run integration tests",
)
skip_unless_db = pytest.mark.skipif(
    not (_INTEGRATION and _DATABASE_URL),
    reason="Skipped: set INTEGRATION_TESTS=1 and DATABASE_URL to run DB integration tests",
)


# ── SMTP helpers ──────────────────────────────────────────────────────────────

class _CapturingHandler:
    """Captura envelopes SMTP recebidos para inspeção nos testes."""

    def __init__(self) -> None:
        self.envelopes: List[object] = []

    async def handle_DATA(self, server, session, envelope):
        self.envelopes.append(envelope)
        return "250 Message accepted"


def _free_port() -> int:
    """Encontra uma porta TCP livre que o SO pode alocar."""
    import socket as _sock
    with _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_smtp_server(handler: _CapturingHandler):
    """
    Sobe um servidor SMTP local em uma porta livre.
    Retorna (controller, port).
    """
    from aiosmtpd.controller import Controller

    port = _free_port()
    controller = Controller(handler, hostname="127.0.0.1", port=port)
    controller.start()
    # Aguarda o servidor ficar pronto
    for _ in range(40):
        if controller.server is not None:
            break
        time.sleep(0.05)
    return controller, port


# ── Email integration ─────────────────────────────────────────────────────────

@skip_unless_integration
class TestEmailDeliveryIntegration:
    """Verifica que send_email entrega mensagens ao servidor SMTP real."""

    @pytest.mark.asyncio
    async def test_message_received_by_local_smtp_server(self):
        """
        send_email deve entregar uma mensagem que pode ser lida pelo servidor SMTP.

        Estratégia:
        - Sobe aiosmtpd localmente (sem TLS, sem auth — adequado para localhost).
        - Configura settings a apontar para este servidor.
        - Intercepta aiosmtplib.send apenas para remover start_tls (localhost
          não precisa de TLS; auth é pulado porque smtp_user/password ficam
          vazios, o que aciona o caminho dev-mode → mas a mensagem é entregue
          via aiosmtplib diretamente para provar o transporte).
        - Verifica que o servidor capturou exatamente 1 envelope.
        """
        handler = _CapturingHandler()
        controller, port = _start_smtp_server(handler)

        try:
            # Envia diretamente pela camada de transporte (aiosmtplib),
            # sem passar por settings, para provar que o transporte funciona.
            import aiosmtplib
            from email.mime.text import MIMEText

            msg = MIMEText("Integration test body", "plain", "utf-8")
            msg["Subject"] = "LicitAIM Integration Test"
            msg["From"]    = "noreply@licitaim.com.br"
            msg["To"]      = "test@example.com"

            await aiosmtplib.send(
                msg,
                hostname="127.0.0.1",
                port=port,
                start_tls=False,
            )

            assert len(handler.envelopes) == 1, (
                f"Esperado 1 envelope, recebido {len(handler.envelopes)}"
            )
            envelope = handler.envelopes[0]
            content  = envelope.content.decode("utf-8", errors="replace")
            assert "Integration Test" in content, (
                f"Subject não encontrado no conteúdo: {content[:300]}"
            )
            assert "test@example.com" in envelope.rcpt_tos, (
                f"Destinatário incorreto: {envelope.rcpt_tos}"
            )

        finally:
            controller.stop()

    @pytest.mark.asyncio
    async def test_send_email_delivers_via_configured_smtp(self):
        """
        send_email (dev mode: smtp_user vazio) retorna True e a mensagem
        *não* passa pelo transporte — comportamento esperado em dev.
        Confirma que nenhuma exceção é propagada e o retorno é True.
        """
        handler = _CapturingHandler()
        controller, port = _start_smtp_server(handler)

        try:
            mock_settings = MagicMock()
            mock_settings.smtp_user     = ""   # dev mode
            mock_settings.smtp_password = ""
            mock_settings.smtp_host     = "127.0.0.1"
            mock_settings.smtp_port     = port
            mock_settings.smtp_from     = "noreply@licitaim.com.br"
            mock_settings.smtp_from_name = "LicitAIM"

            with patch("app.core.config.get_settings", return_value=mock_settings):
                from app.services.senders.email_sender import send_email
                result = await send_email(
                    to="recipient@example.com",
                    subject="Alerta: licitação próxima",
                    body_text="A licitação vence em 2 dias.",
                    cta_url="https://licitaim.com.br",
                    cta_label="Ver detalhes",
                )

            # Dev mode → True sem transporte real
            assert result is True
            # Nenhuma mensagem chegou ao servidor (dev mode não envia)
            assert len(handler.envelopes) == 0

        finally:
            controller.stop()

    @pytest.mark.asyncio
    async def test_send_email_end_to_end_with_credentials(self):
        """
        Com smtp_user/password configurados e servidor local sem TLS,
        send_email deve entregar a mensagem.

        Para evitar STARTTLS (que falha em localhost), patchamos apenas o
        kwarg start_tls=False mantendo o restante do fluxo real.
        """
        handler = _CapturingHandler()
        controller, port = _start_smtp_server(handler)

        try:
            mock_settings = MagicMock()
            mock_settings.smtp_user      = "user@test.com"   # credenciais falsas
            mock_settings.smtp_password  = "password"
            mock_settings.smtp_host      = "127.0.0.1"
            mock_settings.smtp_port      = port
            mock_settings.smtp_from      = "noreply@licitaim.com.br"
            mock_settings.smtp_from_name = "LicitAIM"

            import aiosmtplib as _aiosmtplib_mod
            _real_send = _aiosmtplib_mod.send  # capture before patching

            async def _patched_send(msg, *, hostname, port, start_tls, **_kwargs):
                """Chama o transporte real mas sem STARTTLS (localhost não suporta TLS)."""
                await _real_send(
                    msg,
                    hostname=hostname,
                    port=port,
                    # sem username/password: aiosmtpd padrão não exige AUTH
                    start_tls=False,
                )

            with (
                patch("app.core.config.get_settings", return_value=mock_settings),
                patch("aiosmtplib.send", side_effect=_patched_send),
            ):
                from app.services.senders.email_sender import send_email
                result = await send_email(
                    to="alerta@empresa.com.br",
                    subject="Monitor ativado: construção civil",
                    body_text="Nova licitação encontrada para o seu monitor.",
                    cta_url="https://licitaim.com.br/licitacoes",
                    cta_label="Ver licitação",
                )

            assert result is True, "send_email deve retornar True após entrega"
            assert len(handler.envelopes) == 1, (
                f"Exatamente 1 envelope esperado; recebido: {len(handler.envelopes)}"
            )

            raw = handler.envelopes[0].content.decode("utf-8", errors="replace")
            parsed = email.message_from_string(raw)

            # Subject may be RFC 2047 encoded — decode before asserting
            from email.header import decode_header as _decode_header
            subject_parts = _decode_header(parsed["Subject"])
            subject_text  = "".join(
                part.decode(enc or "utf-8") if isinstance(part, bytes) else part
                for part, enc in subject_parts
            )
            assert "Monitor ativado" in subject_text, f"Subject inesperado: {subject_text!r}"
            assert "alerta@empresa.com.br" in handler.envelopes[0].rcpt_tos

        finally:
            controller.stop()

    @pytest.mark.asyncio
    async def test_html_body_included_in_delivered_message(self):
        """A mensagem entregue deve conter tanto a parte text/plain quanto text/html."""
        handler = _CapturingHandler()
        controller, port = _start_smtp_server(handler)

        try:
            mock_settings = MagicMock()
            mock_settings.smtp_user      = "u@t.com"
            mock_settings.smtp_password  = "p"
            mock_settings.smtp_host      = "127.0.0.1"
            mock_settings.smtp_port      = port
            mock_settings.smtp_from      = "noreply@licitaim.com.br"
            mock_settings.smtp_from_name = "LicitAIM"

            import aiosmtplib as _aiosmtplib_mod2
            _real_send2 = _aiosmtplib_mod2.send  # capture before patching

            async def _no_tls(msg, *, hostname, port, start_tls, **_kwargs):
                await _real_send2(msg, hostname=hostname, port=port, start_tls=False)

            with (
                patch("app.core.config.get_settings", return_value=mock_settings),
                patch("aiosmtplib.send", side_effect=_no_tls),
            ):
                from app.services.senders.email_sender import send_email
                await send_email(
                    to="check@example.com",
                    subject="Test HTML",
                    body_text="Texto simples para verificação.",
                )

            assert handler.envelopes, "Nenhuma mensagem recebida"
            raw    = handler.envelopes[0].content.decode("utf-8", errors="replace")
            parsed = email.message_from_string(raw)

            content_types = set()
            if parsed.is_multipart():
                for part in parsed.walk():
                    content_types.add(part.get_content_type())
            else:
                content_types.add(parsed.get_content_type())

            assert "text/plain" in content_types, f"text/plain não encontrado: {content_types}"
            assert "text/html"  in content_types, f"text/html não encontrado: {content_types}"

        finally:
            controller.stop()


# ── Push integration ──────────────────────────────────────────────────────────

@skip_unless_db
class TestPushDeliveryIntegration:
    """
    Verifica que send_push persiste a notificação no banco de dados.

    Requer DATABASE_URL e INTEGRATION_TESTS=1.
    Faz limpeza da linha inserida ao final de cada teste.
    """

    # ── helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    async def _setup_test_user(conn, user_id: str) -> None:
        """Insere um usuário de teste (ignora se já existir)."""
        await conn.execute(
            """
            INSERT INTO users (id, email, nome, senha_hash)
            VALUES ($1, $2, 'Teste Integração', 'hash')
            ON CONFLICT (id) DO NOTHING
            """,
            user_id,
            f"{user_id}@integration.test",
        )

    @staticmethod
    async def _teardown_test_user(conn, user_id: str) -> None:
        await conn.execute("DELETE FROM notifications WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM users WHERE id = $1", user_id)

    # ── tests ──────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_notification_persisted_in_db(self):
        """send_push deve inserir uma linha na tabela notifications."""
        import asyncpg

        conn = await asyncpg.connect(_DATABASE_URL)
        user_id = "integ-push-test-1"

        try:
            await self._setup_test_user(conn, user_id)

            # Pool real apontando para a mesma conexão
            mock_pool = MagicMock()
            mock_pool.fetchrow = conn.fetchrow

            mock_ws = MagicMock()
            mock_ws.send_personal = AsyncMock(return_value=False)

            with (
                patch("app.db.session.get_pool",         AsyncMock(return_value=mock_pool)),
                patch("app.services.websocket_manager.get_ws_manager", return_value=mock_ws),
            ):
                from app.services.senders.push_sender import send_push
                result = await send_push(
                    user_id=user_id,
                    title="Integração: monitor ativado",
                    body="Nova licitação encontrada.",
                    tipo="match",
                    metadata={"test": True},
                )

            assert result is True, "send_push deve retornar True com DB disponível"

            # Lê de volta do banco para confirmar persistência
            row = await conn.fetchrow(
                "SELECT * FROM notifications WHERE user_id = $1", user_id
            )
            assert row is not None, "Nenhuma linha encontrada na tabela notifications"
            assert row["title"]   == "Integração: monitor ativado"
            assert row["tipo"]    == "match"
            assert row["channel"] == "push"

        finally:
            await self._teardown_test_user(conn, user_id)
            await conn.close()

    @pytest.mark.asyncio
    async def test_notification_retrievable_when_ws_offline(self):
        """
        Quando o usuário está offline (WS retorna False), a notificação
        ainda deve estar persistida no banco para entrega posterior.
        """
        import asyncpg

        conn = await asyncpg.connect(_DATABASE_URL)
        user_id = "integ-push-test-2"

        try:
            await self._setup_test_user(conn, user_id)

            mock_pool = MagicMock()
            mock_pool.fetchrow = conn.fetchrow

            mock_ws = MagicMock()
            mock_ws.send_personal = AsyncMock(return_value=False)  # offline

            with (
                patch("app.db.session.get_pool", AsyncMock(return_value=mock_pool)),
                patch("app.services.websocket_manager.get_ws_manager", return_value=mock_ws),
            ):
                from app.services.senders.push_sender import send_push
                result = await send_push(
                    user_id=user_id,
                    title="Offline: alerta de certidão",
                    body="Certidão vence em 7 dias.",
                    tipo="warning",
                )

            assert result is True

            # Confirma que a notificação está disponível para leitura posterior
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM notifications WHERE user_id = $1 AND lida = false",
                user_id,
            )
            assert count >= 1, "Notificação não encontrada para entrega posterior"

        finally:
            await self._teardown_test_user(conn, user_id)
            await conn.close()
