"""
test_tender_change_service.py

Testes para o serviço que detecta mudanças em licitações favoritadas e
dispara send_tender_update() com o diff correto.

Cobre o caminho de integração:
  tender atualizado → comparação com snapshot → send_tender_update chamado
"""
from __future__ import annotations

import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── constantes de módulo (para patching) ─────────────────────────────────────

CHANGE_SVC = "app.services.tender_change_service"
DB_SESSION  = "app.db.session"
# send_tender_update is accessed via the `_notif_svc` module alias imported inside
# the service function, so we patch it on the notification_service module directly.
NOTIF_SVC   = "app.services.notification_service"
SEND_TENDER_UPDATE_TARGET = f"{NOTIF_SVC}.send_tender_update"


# ── helpers ───────────────────────────────────────────────────────────────────

def _user_row(
    user_id: str = "user-1",
    email: str = "user@example.com",
    nome: str = "Usuário Teste",
    notif_push: bool = True,
    notif_email: bool = True,
    notif_whatsapp: bool = False,
    notif_telegram: bool = False,
    telegram_chat_id: str = "",
    phone: str = "",
) -> dict:
    return {
        "id":               user_id,
        "email":            email,
        "nome":             nome,
        "notif_push":       notif_push,
        "notif_email":      notif_email,
        "notif_whatsapp":   notif_whatsapp,
        "notif_telegram":   notif_telegram,
        "telegram_chat_id": telegram_chat_id,
        "phone":            phone,
    }


def _fav_row(
    fav_id: int = 1,
    user_id: str = "user-1",
    licitacao_id: str = "LICIT-001",
    licitacao_objeto: str = "Aquisição de material de escritório",
    licitacao_orgao: str = "Prefeitura Municipal",
    licitacao_uf: str = "SP",
    licitacao_modalidade: str = "Pregão Eletrônico",
    licitacao_situacao: str = "aberto",
    licitacao_valor: str = "100000.00",
    **user_kwargs,
) -> dict:
    row = {
        "fav_id":              fav_id,
        "user_id":             user_id,
        "licitacao_id":        licitacao_id,
        "licitacao_objeto":    licitacao_objeto,
        "licitacao_orgao":     licitacao_orgao,
        "licitacao_uf":        licitacao_uf,
        "licitacao_modalidade": licitacao_modalidade,
        "licitacao_situacao":  licitacao_situacao,
        "licitacao_valor":     licitacao_valor,
    }
    row.update(_user_row(user_id=user_id, **user_kwargs))
    return row


def _tender(
    licitacao_id: str = "LICIT-001",
    situacao: str = "encerrado",
    valor_estimado: str = "120000.00",
    modalidade: str = "Pregão Eletrônico",
    objeto: str = "Aquisição de material de escritório",
) -> dict:
    return {
        "id":              licitacao_id,
        "situacao":        situacao,
        "valor_estimado":  valor_estimado,
        "modalidade":      modalidade,
        "objeto":          objeto,
    }


def _make_pool(fetch_rows: list[dict] | None = None) -> MagicMock:
    pool = MagicMock()
    pool.fetch   = AsyncMock(return_value=[MagicMock(**r) for r in (fetch_rows or [])])
    pool.execute = AsyncMock(return_value="UPDATE 1")
    return pool


def _make_pool_with_raw(fetch_rows: list[dict] | None = None) -> MagicMock:
    """Pool cujo fetch retorna dicts simples (sem MagicMock wrapping)."""
    pool = MagicMock()
    rows = fetch_rows or []
    # Simula asyncpg.Record: dict() de cada row funciona porque usamos dict(row)
    pool.fetch   = AsyncMock(return_value=rows)
    pool.execute = AsyncMock(return_value="UPDATE 1")
    return pool


# ============================================================================
# _build_diff — testes unitários da função auxiliar
# ============================================================================

class TestBuildDiff:
    """Testa a lógica de diff sem banco de dados."""

    def test_detects_situacao_change(self):
        from app.services.tender_change_service import _build_diff
        tender  = _tender(situacao="encerrado")
        fav_row = _fav_row(licitacao_situacao="aberto")
        diff = _build_diff(tender, fav_row)
        assert "situacao" in diff
        assert diff["situacao"] == ("aberto", "encerrado")

    def test_detects_valor_change(self):
        from app.services.tender_change_service import _build_diff
        tender  = _tender(valor_estimado="150000.00")
        fav_row = _fav_row(licitacao_valor="100000.00")
        diff = _build_diff(tender, fav_row)
        assert "valor_estimado" in diff
        assert diff["valor_estimado"] == ("100000.00", "150000.00")

    def test_detects_modalidade_change(self):
        from app.services.tender_change_service import _build_diff
        tender  = _tender(modalidade="Concorrência")
        fav_row = _fav_row(licitacao_modalidade="Pregão Eletrônico")
        diff = _build_diff(tender, fav_row)
        assert "modalidade" in diff
        assert diff["modalidade"] == ("Pregão Eletrônico", "Concorrência")

    def test_detects_objeto_change(self):
        from app.services.tender_change_service import _build_diff
        tender  = _tender(objeto="Aquisição de equipamentos de TI")
        fav_row = _fav_row(licitacao_objeto="Aquisição de material de escritório")
        diff = _build_diff(tender, fav_row)
        assert "objeto" in diff

    def test_no_diff_when_values_unchanged(self):
        from app.services.tender_change_service import _build_diff
        tender = _tender(
            situacao="aberto",
            valor_estimado="100000.00",
            modalidade="Pregão Eletrônico",
            objeto="Aquisição de material de escritório",
        )
        fav_row = _fav_row(
            licitacao_situacao="aberto",
            licitacao_valor="100000.00",
            licitacao_modalidade="Pregão Eletrônico",
            licitacao_objeto="Aquisição de material de escritório",
        )
        diff = _build_diff(tender, fav_row)
        assert diff == {}, f"Esperado diff vazio, obtido: {diff}"

    def test_multiple_changes_detected_at_once(self):
        from app.services.tender_change_service import _build_diff
        tender  = _tender(situacao="homologado", valor_estimado="200000.00")
        fav_row = _fav_row(licitacao_situacao="aberto", licitacao_valor="100000.00")
        diff = _build_diff(tender, fav_row)
        assert "situacao"       in diff
        assert "valor_estimado" in diff

    def test_ignores_empty_new_value(self):
        """Novo valor vazio não deve gerar diff (não há dado novo para reportar)."""
        from app.services.tender_change_service import _build_diff
        tender  = {"id": "L1", "situacao": "", "valor_estimado": None, "modalidade": "Pregão"}
        fav_row = _fav_row(licitacao_situacao="aberto")
        diff = _build_diff(tender, fav_row)
        # situacao está vazio no tender → não gera diff
        assert "situacao" not in diff

    def test_old_value_none_treated_as_empty_string(self):
        """None no snapshot do favorito é tratado como string vazia para comparação."""
        from app.services.tender_change_service import _build_diff
        tender  = _tender(situacao="suspenso")
        fav_row = _fav_row(licitacao_situacao=None)
        diff = _build_diff(tender, fav_row)
        assert "situacao" in diff
        assert diff["situacao"][0] == ""   # old = ""
        assert diff["situacao"][1] == "suspenso"


# ============================================================================
# notify_favorited_tender_changes — testes de integração (mocked DB)
# ============================================================================

class TestNotifyFavoritedTenderChanges:
    """
    Confirma que send_tender_update() é chamado quando campos da licitação mudam
    e que NÃO é chamado quando nada mudou.
    """

    @pytest.mark.asyncio
    async def test_send_tender_update_called_on_status_change(self):
        """
        Cenário principal: situação muda de 'aberto' para 'encerrado'.
        Deve chamar send_tender_update com diff correto.
        """
        fav = _fav_row(licitacao_situacao="aberto")
        pool = _make_pool_with_raw([fav])

        tender = _tender(situacao="encerrado", valor_estimado="100000.00")

        captured_calls: list[dict] = []

        async def _fake_send_tender_update(user, t, changes, background_tasks=None):
            captured_calls.append({"user": user, "tender": t, "changes": changes})

        with (
            patch(f"{DB_SESSION}.get_pool", AsyncMock(return_value=pool)),
            patch(SEND_TENDER_UPDATE_TARGET, side_effect=_fake_send_tender_update),
        ):
            from app.services.tender_change_service import notify_favorited_tender_changes
            result = await notify_favorited_tender_changes(tender)

        assert result["users_notified"] == 1, f"Esperado 1 notificado, obtido: {result}"
        assert len(captured_calls) == 1

        changes = captured_calls[0]["changes"]
        assert "situacao" in changes, f"'situacao' não está no diff: {changes}"
        assert changes["situacao"] == ("aberto", "encerrado")

    @pytest.mark.asyncio
    async def test_send_tender_update_called_on_value_change(self):
        """Valor estimado aumenta — send_tender_update deve ser chamado com o diff de valor."""
        fav = _fav_row(licitacao_valor="100000.00", licitacao_situacao="aberto")
        pool = _make_pool_with_raw([fav])

        tender = _tender(situacao="aberto", valor_estimado="180000.00")

        captured_calls: list[dict] = []

        async def _fake(user, t, changes, background_tasks=None):
            captured_calls.append(changes)

        with (
            patch(f"{DB_SESSION}.get_pool", AsyncMock(return_value=pool)),
            patch(SEND_TENDER_UPDATE_TARGET, side_effect=_fake),
        ):
            from app.services.tender_change_service import notify_favorited_tender_changes
            result = await notify_favorited_tender_changes(tender)

        assert result["users_notified"] == 1
        assert "valor_estimado" in captured_calls[0]
        assert captured_calls[0]["valor_estimado"] == ("100000.00", "180000.00")

    @pytest.mark.asyncio
    async def test_no_notification_when_nothing_changed(self):
        """Snapshot idêntico aos novos dados → send_tender_update NÃO deve ser chamado."""
        fav = _fav_row(
            licitacao_situacao="aberto",
            licitacao_valor="100000.00",
            licitacao_modalidade="Pregão Eletrônico",
            licitacao_objeto="Aquisição de material de escritório",
        )
        pool = _make_pool_with_raw([fav])

        tender = _tender(
            situacao="aberto",
            valor_estimado="100000.00",
            modalidade="Pregão Eletrônico",
            objeto="Aquisição de material de escritório",
        )

        mock_send = AsyncMock()

        with (
            patch(f"{DB_SESSION}.get_pool", AsyncMock(return_value=pool)),
            patch(SEND_TENDER_UPDATE_TARGET, mock_send),
        ):
            from app.services.tender_change_service import notify_favorited_tender_changes
            result = await notify_favorited_tender_changes(tender)

        mock_send.assert_not_awaited()
        assert result["users_notified"] == 0
        assert result["users_skipped"]  == 1

    @pytest.mark.asyncio
    async def test_multiple_users_all_notified(self):
        """
        Dois usuários favoritaram a mesma licitação.
        Ambos devem receber notificação quando o status muda.
        """
        fav1 = _fav_row(fav_id=1, user_id="user-1", licitacao_situacao="aberto")
        fav2 = _fav_row(fav_id=2, user_id="user-2", email="u2@example.com",
                        licitacao_situacao="aberto")
        pool = _make_pool_with_raw([fav1, fav2])

        tender = _tender(situacao="homologado")

        notified_users: list[str] = []

        async def _fake(user, t, changes, background_tasks=None):
            notified_users.append(user["id"])

        with (
            patch(f"{DB_SESSION}.get_pool", AsyncMock(return_value=pool)),
            patch(SEND_TENDER_UPDATE_TARGET, side_effect=_fake),
        ):
            from app.services.tender_change_service import notify_favorited_tender_changes
            result = await notify_favorited_tender_changes(tender)

        assert result["users_notified"] == 2
        assert set(notified_users) == {"user-1", "user-2"}

    @pytest.mark.asyncio
    async def test_diff_passed_correctly_for_multiple_changed_fields(self):
        """
        Status e valor mudam ao mesmo tempo.
        O diff deve conter ambos os campos com os valores corretos.
        """
        fav = _fav_row(licitacao_situacao="aberto", licitacao_valor="100000.00")
        pool = _make_pool_with_raw([fav])

        tender = _tender(situacao="suspenso", valor_estimado="0.00")
        # "0.00" é uma string não-vazia → deve gerar diff para valor

        captured: list[dict] = []

        async def _fake(user, t, changes, background_tasks=None):
            captured.append(changes)

        with (
            patch(f"{DB_SESSION}.get_pool", AsyncMock(return_value=pool)),
            patch(SEND_TENDER_UPDATE_TARGET, side_effect=_fake),
        ):
            from app.services.tender_change_service import notify_favorited_tender_changes
            result = await notify_favorited_tender_changes(tender)

        assert result["users_notified"] == 1
        diff = captured[0]
        assert "situacao"       in diff, f"Esperado 'situacao' em diff: {diff}"
        assert "valor_estimado" in diff, f"Esperado 'valor_estimado' em diff: {diff}"
        assert diff["situacao"][0]       == "aberto"
        assert diff["situacao"][1]       == "suspenso"
        assert diff["valor_estimado"][0] == "100000.00"
        assert diff["valor_estimado"][1] == "0.00"

    @pytest.mark.asyncio
    async def test_returns_zero_counts_when_no_favorites(self):
        """Nenhum usuário favoritou → resultado deve ter zeros."""
        pool = _make_pool_with_raw([])   # fetch retorna lista vazia
        tender = _tender()
        mock_send = AsyncMock()

        with (
            patch(f"{DB_SESSION}.get_pool", AsyncMock(return_value=pool)),
            patch(SEND_TENDER_UPDATE_TARGET, mock_send),
        ):
            from app.services.tender_change_service import notify_favorited_tender_changes
            result = await notify_favorited_tender_changes(tender)

        mock_send.assert_not_awaited()
        assert result == {"users_checked": 0, "users_notified": 0, "users_skipped": 0}

    @pytest.mark.asyncio
    async def test_tender_without_id_is_ignored(self):
        """Um tender sem 'id' ou 'numero' não deve consultar o banco."""
        pool = MagicMock()
        pool.fetch = AsyncMock()

        with patch(f"{DB_SESSION}.get_pool", AsyncMock(return_value=pool)):
            from app.services.tender_change_service import notify_favorited_tender_changes
            result = await notify_favorited_tender_changes({})

        pool.fetch.assert_not_awaited()
        assert result["users_checked"] == 0

    @pytest.mark.asyncio
    async def test_user_dict_forwarded_to_send_tender_update(self):
        """
        O user dict passado para send_tender_update deve ter os campos
        esperados pela notification_service (id, email, notif_push, etc.)
        """
        fav = _fav_row(
            user_id="user-42",
            email="test@domain.com",
            notif_push=True,
            notif_email=False,
            licitacao_situacao="aberto",
        )
        pool = _make_pool_with_raw([fav])

        tender = _tender(situacao="encerrado")

        captured_user: list[dict] = []

        async def _fake(user, t, changes, background_tasks=None):
            captured_user.append(user)

        with (
            patch(f"{DB_SESSION}.get_pool", AsyncMock(return_value=pool)),
            patch(SEND_TENDER_UPDATE_TARGET, side_effect=_fake),
        ):
            from app.services.tender_change_service import notify_favorited_tender_changes
            await notify_favorited_tender_changes(tender)

        assert len(captured_user) == 1
        u = captured_user[0]
        assert u["id"]          == "user-42"
        assert u["email"]       == "test@domain.com"
        assert u["notif_push"]  is True
        assert u["notif_email"] is False

    @pytest.mark.asyncio
    async def test_snapshot_update_attempted_after_notification(self):
        """
        Após notificar, o serviço deve tentar actualizar o snapshot no banco
        (para que o próximo run não reenvia a mesma mudança).
        """
        fav = _fav_row(licitacao_situacao="aberto")
        pool = _make_pool_with_raw([fav])

        tender = _tender(situacao="encerrado")

        async def _fake(user, t, changes, background_tasks=None):
            pass

        with (
            patch(f"{DB_SESSION}.get_pool", AsyncMock(return_value=pool)),
            patch(SEND_TENDER_UPDATE_TARGET, side_effect=_fake),
        ):
            from app.services.tender_change_service import notify_favorited_tender_changes
            await notify_favorited_tender_changes(tender)

        # pool.execute deve ter sido chamado ao menos uma vez para actualizar o favorito
        pool.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_background_tasks_forwarded_to_send_tender_update(self):
        """Quando background_tasks é fornecido, deve ser repassado ao send_tender_update."""
        fav = _fav_row(licitacao_situacao="aberto")
        pool = _make_pool_with_raw([fav])

        tender = _tender(situacao="encerrado")
        bg = MagicMock()

        captured_bg: list = []

        async def _fake(user, t, changes, background_tasks=None):
            captured_bg.append(background_tasks)

        with (
            patch(f"{DB_SESSION}.get_pool", AsyncMock(return_value=pool)),
            patch(SEND_TENDER_UPDATE_TARGET, side_effect=_fake),
        ):
            from app.services.tender_change_service import notify_favorited_tender_changes
            await notify_favorited_tender_changes(tender, background_tasks=bg)

        assert len(captured_bg) == 1
        assert captured_bg[0] is bg

    @pytest.mark.asyncio
    async def test_users_skipped_count_correct_when_mixed(self):
        """
        3 usuários: 2 têm mudanças, 1 não tem.
        Contagens devem refletir isso.
        """
        fav_changed_1 = _fav_row(fav_id=1, user_id="u1", licitacao_situacao="aberto")
        fav_changed_2 = _fav_row(fav_id=2, user_id="u2", email="u2@x.com",
                                  licitacao_situacao="aberto")
        fav_same      = _fav_row(fav_id=3, user_id="u3", email="u3@x.com",
                                  licitacao_situacao="encerrado",  # já é encerrado
                                  licitacao_valor="100000.00",
                                  licitacao_modalidade="Pregão Eletrônico",
                                  licitacao_objeto="Aquisição de material de escritório")
        pool = _make_pool_with_raw([fav_changed_1, fav_changed_2, fav_same])

        # Tender novo tem situacao=encerrado, mas fav_same já tinha encerrado
        tender = _tender(
            situacao="encerrado",
            valor_estimado="100000.00",
            modalidade="Pregão Eletrônico",
            objeto="Aquisição de material de escritório",
        )

        async def _fake(user, t, changes, background_tasks=None):
            pass

        with (
            patch(f"{DB_SESSION}.get_pool", AsyncMock(return_value=pool)),
            patch(SEND_TENDER_UPDATE_TARGET, side_effect=_fake),
        ):
            from app.services.tender_change_service import notify_favorited_tender_changes
            result = await notify_favorited_tender_changes(tender)

        assert result["users_checked"]  == 3
        assert result["users_notified"] == 2
        assert result["users_skipped"]  == 1

    @pytest.mark.asyncio
    async def test_send_tender_update_returning_false_counts_as_skipped(self):
        """
        Quando send_tender_update retorna False (dedup atômico via ON CONFLICT),
        o usuário deve ser contado em users_skipped, não em users_notified,
        e o snapshot NÃO deve ser atualizado.
        """
        fav = _fav_row(licitacao_situacao="aberto")
        pool = _make_pool_with_raw([fav])

        tender = _tender(situacao="encerrado")

        async def _deduped(user, t, changes, background_tasks=None):
            return False  # simula dedup atômico

        with (
            patch(f"{DB_SESSION}.get_pool", AsyncMock(return_value=pool)),
            patch(SEND_TENDER_UPDATE_TARGET, side_effect=_deduped),
        ):
            from app.services.tender_change_service import notify_favorited_tender_changes
            result = await notify_favorited_tender_changes(tender)

        assert result["users_notified"] == 0, (
            "Alerta deduplicado não deve incrementar users_notified"
        )
        assert result["users_skipped"]  == 1, (
            "Alerta deduplicado deve incrementar users_skipped"
        )
        # Snapshot não deve ser atualizado quando dedup foi ativado
        pool.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dedup_does_not_affect_different_users(self):
        """
        Dedup de send_tender_update para um usuário não deve suprimir a
        notificação de outro usuário que favoritou a mesma licitação.
        """
        fav1 = _fav_row(fav_id=1, user_id="user-1", licitacao_situacao="aberto")
        fav2 = _fav_row(fav_id=2, user_id="user-2", email="u2@x.com",
                        licitacao_situacao="aberto")
        pool = _make_pool_with_raw([fav1, fav2])

        tender = _tender(situacao="encerrado")

        call_count = 0

        async def _first_deduped_second_ok(user, t, changes, background_tasks=None):
            nonlocal call_count
            call_count += 1
            # Primeiro usuário: dedup ativado; segundo: ok
            return False if call_count == 1 else True

        with (
            patch(f"{DB_SESSION}.get_pool", AsyncMock(return_value=pool)),
            patch(SEND_TENDER_UPDATE_TARGET, side_effect=_first_deduped_second_ok),
        ):
            from app.services.tender_change_service import notify_favorited_tender_changes
            result = await notify_favorited_tender_changes(tender)

        assert result["users_checked"]  == 2
        assert result["users_notified"] == 1
        assert result["users_skipped"]  == 1


# ============================================================================
# Testes de deduplicação atômica em send_tender_update
# ============================================================================

class TestSendTenderUpdateAtomicDedup:
    """
    Confirma que send_tender_update usa fetchval com ON CONFLICT DO NOTHING
    e retorna False quando o INSERT não produz nenhuma linha (dedup ativado).
    """

    @pytest.mark.asyncio
    async def test_returns_false_when_insert_conflicts(self):
        """
        Quando fetchval retorna None (conflito na dedup_key), send_tender_update
        deve retornar False sem chamar send().
        """
        pool = MagicMock()
        # fetchval retorna None → simula ON CONFLICT DO NOTHING (nenhuma linha inserida)
        pool.fetchval = AsyncMock(return_value=None)

        mock_send = AsyncMock()

        with (
            patch("app.db.session.get_pool", AsyncMock(return_value=pool)),
            patch("app.services.notification_service.send", mock_send),
        ):
            from app.services.notification_service import send_tender_update
            result = await send_tender_update(
                user=_user_row(),
                tender=_tender(),
                changes={"situacao": ("aberto", "encerrado")},
            )

        assert result is False, (
            f"Esperado False quando INSERT conflita, obtido: {result!r}"
        )
        mock_send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_true_when_insert_succeeds(self):
        """
        Quando fetchval retorna um id (linha inserida), send_tender_update deve
        retornar True e chamar send() para os canais externos.
        """
        pool = MagicMock()
        # fetchval retorna id → INSERT bem-sucedido
        pool.fetchval = AsyncMock(return_value=42)

        mock_send = AsyncMock()

        with (
            patch("app.db.session.get_pool", AsyncMock(return_value=pool)),
            patch("app.services.notification_service.send", mock_send),
        ):
            from app.services.notification_service import send_tender_update
            result = await send_tender_update(
                user=_user_row(),
                tender=_tender(),
                changes={"situacao": ("aberto", "encerrado")},
            )

        assert result is True, (
            f"Esperado True quando INSERT insere uma linha, obtido: {result!r}"
        )
        mock_send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dedup_key_covers_5_minute_bucket(self):
        """
        Dois calls dentro do mesmo bucket de 5 minutos produzem o mesmo dedup_key.
        Confirma que o fetchval é chamado com o mesmo $6 em ambas as chamadas.
        """
        import time

        pool = MagicMock()
        captured_keys: list[str] = []

        async def _capture(*args):
            # $6 é o dedup_key (sexto argumento posicional após a query)
            captured_keys.append(args[6])
            return 42  # primeiro call bem-sucedido

        pool.fetchval = _capture

        mock_send = AsyncMock()

        user   = _user_row()
        tender = _tender()
        diff   = {"situacao": ("aberto", "encerrado")}

        with (
            patch("app.db.session.get_pool", AsyncMock(return_value=pool)),
            patch("app.services.notification_service.send", mock_send),
        ):
            from app.services.notification_service import send_tender_update
            await send_tender_update(user, tender, diff)
            await send_tender_update(user, tender, diff)

        assert len(captured_keys) == 2
        assert captured_keys[0] == captured_keys[1], (
            "Dois calls no mesmo bucket de 5min devem compartilhar o mesmo dedup_key; "
            f"obtido: {captured_keys}"
        )


# ============================================================================
# Testes de integração — cadeia de produção
#   upsert_licitacoes (detecção de mudança)
#   → cache_scheduler dispara notify_favorited_tender_changes
#   → send_tender_update chamado com diff correto
# ============================================================================

class TestUpsertChangeDetectionIntegration:
    """
    Verifica que a função de produção upsert_licitacoes detecta corretamente
    quando um tender existente tem campos rastreados alterados e retorna o
    tender na lista de changed_tenders.
    """

    def _make_conn(
        self,
        prefetch_rows: list[dict],
        upsert_inserted: bool,
    ) -> MagicMock:
        """
        Monta um mock de asyncpg.Connection com:
          - fetch()      → retorna os snapshots pre-existentes (pre-fetch)
          - fetchrow()   → retorna {"inserted": upsert_inserted} (resultado do upsert)
        """
        conn = MagicMock()
        # pre-fetch retorna lista de Records — usamos dicts simples
        conn.fetch = AsyncMock(return_value=prefetch_rows)
        conn.fetchrow = AsyncMock(return_value={"inserted": upsert_inserted})
        return conn

    def _make_pool_with_conn(self, conn: MagicMock) -> MagicMock:
        pool = MagicMock()
        # pool.acquire() é um context manager assíncrono que entrega conn
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__  = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=cm)
        return pool

    @pytest.mark.asyncio
    async def test_upsert_returns_changed_tender_when_situacao_changes(self):
        """
        Quando upsert_licitacoes atualiza (xmax≠0) e a situação mudou,
        o tender deve aparecer em changed_tenders.
        """
        # Snapshot existente no banco: situacao=aberto
        old_row = {
            "numero":          "LICIT-999",
            "situacao":        "aberto",
            "valor_estimado":  "100000.00",
            "modalidade":      "Pregão Eletrônico",
            "objeto":          "Aquisição de material de escritório",
        }
        conn = self._make_conn(prefetch_rows=[old_row], upsert_inserted=False)
        pool = self._make_pool_with_conn(conn)

        # Novo dado do tender: situacao=encerrado (mudança!)
        new_item = {
            "numero":          "LICIT-999",
            "situacao":        "encerrado",
            "valor_estimado":  100000.00,
            "modalidade":      "Pregão Eletrônico",
            "objeto":          "Aquisição de material de escritório",
        }

        # Habilita o cache para a função não retornar cedo
        with patch("app.db.licitacoes_repo._cache_ready", True):
            from app.db.licitacoes_repo import upsert_licitacoes
            inseridos, atualizados, changed = await upsert_licitacoes(pool, [new_item])

        assert inseridos   == 0
        assert atualizados == 1
        assert len(changed) == 1, f"Esperado 1 tender changed, got: {changed}"
        assert changed[0]["numero"]   == "LICIT-999"
        assert changed[0]["situacao"] == "encerrado"

    @pytest.mark.asyncio
    async def test_upsert_returns_empty_changed_when_nothing_differs(self):
        """
        Quando os campos rastreados são idênticos ao snapshot, changed_tenders
        deve estar vazio mesmo que a linha tenha sido atualizada.
        """
        old_row = {
            "numero":         "LICIT-888",
            "situacao":       "aberto",
            "valor_estimado": "100000.0",
            "modalidade":     "Pregão Eletrônico",
            "objeto":         "Material de limpeza",
        }
        conn = self._make_conn(prefetch_rows=[old_row], upsert_inserted=False)
        pool = self._make_pool_with_conn(conn)

        same_item = {
            "numero":          "LICIT-888",
            "situacao":        "aberto",
            "valor_estimado":  100000.0,
            "modalidade":      "Pregão Eletrônico",
            "objeto":          "Material de limpeza",
        }

        with patch("app.db.licitacoes_repo._cache_ready", True):
            from app.db.licitacoes_repo import upsert_licitacoes
            inseridos, atualizados, changed = await upsert_licitacoes(pool, [same_item])

        assert atualizados == 1
        assert changed     == [], f"Esperado vazio, obtido: {changed}"

    @pytest.mark.asyncio
    async def test_upsert_does_not_flag_new_inserts_as_changed(self):
        """
        Itens inseridos pela primeira vez (sem snapshot no banco) não devem
        aparecer em changed_tenders — não há mudança, é uma criação nova.
        """
        # pre-fetch retorna vazio → tender não existia antes
        conn = self._make_conn(prefetch_rows=[], upsert_inserted=True)
        pool = self._make_pool_with_conn(conn)

        new_item = {
            "numero":    "LICIT-777",
            "situacao":  "aberto",
            "objeto":    "Computadores",
        }

        with patch("app.db.licitacoes_repo._cache_ready", True):
            from app.db.licitacoes_repo import upsert_licitacoes
            inseridos, atualizados, changed = await upsert_licitacoes(pool, [new_item])

        assert inseridos == 1
        assert changed   == []

    @pytest.mark.asyncio
    async def test_upsert_detects_valor_change_across_numeric_representations(self):
        """
        Mudança de valor estimado deve ser detectada mesmo quando o banco
        retorna string decimal e o item traz float.
        """
        old_row = {
            "numero":         "LICIT-666",
            "situacao":       "aberto",
            "valor_estimado": "100000.00",
            "modalidade":     "Pregão",
            "objeto":         "Serviços de TI",
        }
        conn = self._make_conn(prefetch_rows=[old_row], upsert_inserted=False)
        pool = self._make_pool_with_conn(conn)

        updated_item = {
            "numero":          "LICIT-666",
            "situacao":        "aberto",
            "valor_estimado":  200000.0,   # mudou de 100000 para 200000
            "modalidade":      "Pregão",
            "objeto":          "Serviços de TI",
        }

        with patch("app.db.licitacoes_repo._cache_ready", True):
            from app.db.licitacoes_repo import upsert_licitacoes
            _, _, changed = await upsert_licitacoes(pool, [updated_item])

        assert len(changed) == 1
        assert changed[0]["valor_estimado"] == 200000.0


class TestCacheSchedulerNotificationWiring:
    """
    Verifica que _safe_notify_change (chamado pelo sync job quando changed_tenders
    não está vazio) chega até send_tender_update para um usuário que favoritou
    a licitação alterada.
    """

    @pytest.mark.asyncio
    async def test_safe_notify_change_reaches_send_tender_update(self):
        """
        Teste de integração do caminho completo de produção:
          cache_scheduler._safe_notify_change(tender)
          → notify_favorited_tender_changes(tender)
          → send_tender_update(user, tender, diff)

        Usa mocks no banco e no sender para isolar I/O externo.
        """
        # Um usuário favoritou LICIT-999 com situacao=aberto
        fav = {
            "fav_id":               1,
            "user_id":              "user-prod-test",
            "licitacao_id":         "LICIT-999",
            "licitacao_objeto":     "Reforma de escola",
            "licitacao_orgao":      "Prefeitura",
            "licitacao_uf":         "SP",
            "licitacao_modalidade": "Pregão Eletrônico",
            "licitacao_situacao":   "aberto",
            "licitacao_valor":      "50000.00",
            "id":                   "user-prod-test",
            "email":                "prod@test.com",
            "nome":                 "Usuário Prod",
            "notif_push":           True,
            "notif_email":          True,
            "notif_whatsapp":       False,
            "notif_telegram":       False,
            "telegram_chat_id":     "",
            "phone":                "",
        }

        # O tender que o cache_scheduler acabou de processar (situacao mudou)
        changed_tender = {
            "numero":    "LICIT-999",
            "id":        "LICIT-999",
            "situacao":  "encerrado",
            "objeto":    "Reforma de escola",
        }

        notif_pool = MagicMock()
        notif_pool.fetch   = AsyncMock(return_value=[fav])
        notif_pool.execute = AsyncMock(return_value="UPDATE 1")

        send_tender_calls: list[dict] = []

        async def _fake_send_tender_update(user, tender, changes, background_tasks=None):
            send_tender_calls.append({
                "user_id": user["id"],
                "changes": changes,
            })

        with (
            patch(f"{DB_SESSION}.get_pool", AsyncMock(return_value=notif_pool)),
            patch(SEND_TENDER_UPDATE_TARGET, side_effect=_fake_send_tender_update),
        ):
            from app.services.cache_scheduler import _safe_notify_change
            await _safe_notify_change(changed_tender)

        assert len(send_tender_calls) == 1, (
            f"Esperado 1 chamada a send_tender_update, obtido {len(send_tender_calls)}"
        )
        call_info = send_tender_calls[0]
        assert call_info["user_id"] == "user-prod-test"
        assert "situacao" in call_info["changes"], (
            f"'situacao' deveria estar no diff: {call_info['changes']}"
        )
        assert call_info["changes"]["situacao"] == ("aberto", "encerrado")

    @pytest.mark.asyncio
    async def test_safe_notify_change_finds_favorite_stored_by_pncp_id_when_numero_differs(self):
        """
        Cobre o caso real PNCP em que id (portal purchase ID) ≠ numero (numeroControlePNCP).

        O frontend armazena lic.id como licitacao_id. O scheduler entrega o tender
        com numero=numeroControlePNCP e id=portal_purchase_id (podem diferir).
        notify_favorited_tender_changes deve encontrar o favorito via ANY([$id, $numero]).
        """
        portal_id    = "pncp-portal-purchase-42"    # valor que o frontend armazenou
        numero_pncp  = "12345678000100-2024-001234"  # numeroControlePNCP — diferente!

        fav = {
            "fav_id":               2,
            "user_id":              "user-pncp-test",
            # ↓ Frontend gravou lic.id (portal ID), não o numero PNCP
            "licitacao_id":         portal_id,
            "licitacao_objeto":     "Serviços de TI",
            "licitacao_orgao":      "Ministério do Planejamento",
            "licitacao_uf":         "DF",
            "licitacao_modalidade": "Pregão Eletrônico",
            "licitacao_situacao":   "aberto",
            "licitacao_valor":      "999000.00",
            "id":                   "user-pncp-test",
            "email":                "pncp@test.com",
            "nome":                 "Usuário PNCP",
            "notif_push":           True,
            "notif_email":          True,
            "notif_whatsapp":       False,
            "notif_telegram":       False,
            "telegram_chat_id":     "",
            "phone":                "",
        }

        # O scheduler entrega o tender com numero ≠ id
        changed_tender = {
            "numero":   numero_pncp,
            "id":       portal_id,
            "situacao": "homologado",   # mudou de "aberto"
            "objeto":   "Serviços de TI",
        }

        notif_pool = MagicMock()
        notif_pool.fetch   = AsyncMock(return_value=[fav])
        notif_pool.execute = AsyncMock(return_value="UPDATE 1")

        send_calls: list[dict] = []

        async def _fake(user, tender, changes, background_tasks=None):
            send_calls.append({"user_id": user["id"], "changes": changes})

        with (
            patch(f"{DB_SESSION}.get_pool", AsyncMock(return_value=notif_pool)),
            patch(SEND_TENDER_UPDATE_TARGET, side_effect=_fake),
        ):
            from app.services.cache_scheduler import _safe_notify_change
            await _safe_notify_change(changed_tender)

        assert len(send_calls) == 1, (
            f"Favorito gravado com portal_id deve ser encontrado mesmo quando "
            f"notify usa numero_pncp. Chamadas: {send_calls}"
        )
        assert send_calls[0]["user_id"] == "user-pncp-test"
        assert "situacao" in send_calls[0]["changes"]
        assert send_calls[0]["changes"]["situacao"][1] == "homologado"

        # Confirma que o pool.fetch foi chamado com AMBOS os candidatos de ID
        called_with = notif_pool.fetch.call_args
        candidate_ids_arg = called_with[0][1]  # segundo argumento posicional
        assert portal_id   in candidate_ids_arg, "portal_id deve ser candidato"
        assert numero_pncp in candidate_ids_arg, "numero_pncp deve ser candidato"

    @pytest.mark.asyncio
    async def test_safe_notify_change_does_not_raise_on_db_error(self):
        """
        _safe_notify_change deve absorver erros e não propagar exceções,
        pois é executado como fire-and-forget via asyncio.create_task.
        """
        with patch(f"{DB_SESSION}.get_pool", AsyncMock(side_effect=RuntimeError("DB down"))):
            from app.services.cache_scheduler import _safe_notify_change
            # Não deve levantar exceção
            await _safe_notify_change({"numero": "LICIT-X", "situacao": "aberto"})


