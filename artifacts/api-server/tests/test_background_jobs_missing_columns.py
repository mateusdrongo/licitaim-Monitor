"""
test_background_jobs_missing_columns.py

Testa dois cenários de degradação de schema para os três background jobs de alerta
(check_all_monitors, check_upcoming_tenders, check_document_expirations) e o job
de prazos de tarefas (check_task_deadlines):

1. Colunas de notificação ausentes na tabela `users`
   - O job cai no caminho de fallback (_fetch_with_notif_fallback) e usa
     preferências padrão em vez de abortar.

2. Falha no INSERT da tabela `alertas` (schema drift — coluna ausente)
   - O job NÃO conta o registro como enviado (alerts_sent permanece correto).
   - Um warning é registrado.
   - O job continua processando os demais registros.

Cada teste:
  1. Simula um pool que lança exceção no ponto relevante.
  2. Verifica que o job retorna um dicionário de resumo válido (sem exceção).
  3. Verifica contagens corretas (sem valores positivos enganosos).
  4. Verifica que um warning foi registrado.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Módulos a serem patchados.
# get_pool e funções de notificação são importados *dentro* dos corpos das
# funções async (lazy imports), então patchamos nos módulos originais.
# ---------------------------------------------------------------------------
DB_SESSION_MODULE        = "app.db.session"
NOTIF_SERVICE_MODULE     = "app.services.notification_service"


# ---------------------------------------------------------------------------
# Helpers para criar mocks de pool e de rows do asyncpg
# ---------------------------------------------------------------------------

def _make_row(**kwargs) -> dict:
    """Cria um objeto que se comporta como asyncpg.Record (acesso por chave)."""
    class _Row(dict):
        pass
    return _Row(**kwargs)


def _make_pool(
    *,
    fetch_side_effects: list | None = None,
    fetchval_return=None,
) -> MagicMock:
    """
    Constrói um mock de asyncpg Pool.

    Parâmetros
    ----------
    fetch_side_effects : list
        Lista de valores/exceções retornados em sequência por ``pool.fetch``.
        Use uma exceção para simular coluna ausente; use [] para lista vazia.
    fetchval_return :
        Valor retornado por ``pool.fetchval`` (None = sem dedup existente).
    """
    pool = MagicMock()

    if fetch_side_effects is not None:
        pool.fetch = AsyncMock(side_effect=fetch_side_effects)
    else:
        pool.fetch = AsyncMock(return_value=[])

    pool.fetchval = AsyncMock(return_value=fetchval_return)
    pool.execute  = AsyncMock(return_value="OK")
    return pool


# ===========================================================================
# check_all_monitors
# ===========================================================================

class TestCheckAllMonitors:
    """Testa check_all_monitors com e sem colunas de notificação."""

    @pytest.mark.asyncio
    async def test_returns_valid_summary_when_columns_present(self):
        """Com colunas disponíveis e zero monitores retorna resumo válido."""
        pool = _make_pool(fetch_side_effects=[[]])  # zero monitores

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_SERVICE_MODULE}.send_monitor_match", AsyncMock()),
        ):
            from app.services.monitor_worker import check_all_monitors
            result = await check_all_monitors()

        assert "monitors_checked" in result
        assert "matches_found" in result
        assert result["monitors_checked"] == 0
        assert result["matches_found"] == 0

    @pytest.mark.asyncio
    async def test_falls_back_to_defaults_when_notif_columns_missing(self, caplog):
        """
        Quando a query com colunas notif falha, o job deve:
        - logar um warning mencionando colunas de notificação
        - executar com preferências padrão
        - retornar resumo válido sem lançar exceção
        """
        missing_col_exc = Exception("column u.notif_email does not exist")

        monitor_row = _make_row(
            id=1, user_id=10, nome="Monitor Teste",
            palavras_chave='["software"]', modalidades="[]", ufs="[]",
            valor_min=None, valor_max=None, last_checked_at=None,
            email="user@example.com", user_nome="Usuário Teste",
        )

        pool = _make_pool(
            fetch_side_effects=[
                missing_col_exc,  # 1ª fetch: query com notif colunas → falha
                [monitor_row],    # 2ª fetch: fallback sem notif colunas
                [],               # 3ª fetch: _search_cache → vazio
                [],               # 4ª fetch: dedup alertas
            ]
        )

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_SERVICE_MODULE}.send_monitor_match", AsyncMock()),
            caplog.at_level(logging.WARNING, logger="licitaim.monitor_worker"),
        ):
            from app.services.monitor_worker import check_all_monitors
            result = await check_all_monitors()

        assert "monitors_checked" in result
        assert "matches_found" in result
        assert isinstance(result["monitors_checked"], int)
        assert isinstance(result["matches_found"], int)

        warning_text = " ".join(caplog.messages)
        assert any(
            kw in warning_text.lower()
            for kw in ("notif", "padrão", "indispon", "default")
        ), f"Warning esperado sobre colunas de notificação. Mensagens: {caplog.messages}"

    @pytest.mark.asyncio
    async def test_uses_default_notif_prefs_in_fallback(self, caplog):
        """
        No caminho de fallback, as preferências padrão devem ser aplicadas:
        notif_email=True, notif_push=True, notif_whatsapp=False, notif_telegram=False.
        """
        now = datetime.now(timezone.utc)
        missing_col_exc = Exception("column u.notif_email does not exist")

        monitor_row = _make_row(
            id=2, user_id=20, nome="Monitor Padrão",
            palavras_chave='["construção"]', modalidades="[]", ufs='["SP"]',
            valor_min=None, valor_max=None,
            last_checked_at=now - timedelta(hours=1),
            email="dev@example.com", user_nome="Dev Teste",
        )

        tender_row = _make_row(
            numero="2024/001", objeto="Construção de escola",
            orgao_nome="Prefeitura SP", uf="SP", modalidade="pregao",
            valor_estimado=500000.0,
            data_abertura=now + timedelta(days=5),
            data_publicacao=now - timedelta(hours=30),
        )

        pool = _make_pool(
            fetch_side_effects=[
                missing_col_exc,   # query com notif colunas → falha
                [monitor_row],     # fallback sem notif colunas
                [tender_row],      # _search_cache → 1 resultado
                [],                # dedup alertas → nenhum já enviado
            ]
        )

        captured_users: list[dict] = []

        async def _fake_send(user, monitor, tender):
            captured_users.append(dict(user))
            return True  # simula INSERT persistido com sucesso

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_SERVICE_MODULE}.send_monitor_match", side_effect=_fake_send),
        ):
            from app.services.monitor_worker import check_all_monitors
            result = await check_all_monitors()

        assert result["matches_found"] >= 1, "Deve ter encontrado o tender"
        assert len(captured_users) >= 1, "send_monitor_match deve ter sido chamado"

        u = captured_users[0]
        assert u["notif_email"]     is True
        assert u["notif_push"]      is True
        assert u["notif_whatsapp"]  is False
        assert u["notif_telegram"]  is False

    @pytest.mark.asyncio
    async def test_no_exception_raised_when_columns_missing(self):
        """O job não deve propagar exceção quando colunas de notif estão ausentes."""
        missing_col_exc = Exception("column u.notif_push does not exist")
        pool = _make_pool(
            fetch_side_effects=[missing_col_exc, [], [], []]
        )

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_SERVICE_MODULE}.send_monitor_match", AsyncMock()),
        ):
            from app.services.monitor_worker import check_all_monitors
            result = await check_all_monitors()

        assert isinstance(result, dict)
        assert "monitors_checked" in result


# ===========================================================================
# check_upcoming_tenders
# ===========================================================================

class TestCheckUpcomingTenders:
    """Testa check_upcoming_tenders com e sem colunas de notificação."""

    @pytest.mark.asyncio
    async def test_returns_valid_summary_when_no_upcoming(self):
        """Sem licitações próximas retorna resumo zerado."""
        pool = _make_pool(fetch_side_effects=[[]])

        with patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)):
            from app.services.monitor_worker import check_upcoming_tenders
            result = await check_upcoming_tenders()

        assert result["tenders_checked"] == 0
        assert result["notifications_sent"] == 0
        assert result["notifications_skipped"] == 0

    @pytest.mark.asyncio
    async def test_falls_back_to_defaults_when_notif_columns_missing(self, caplog):
        """
        Quando a query de favoritos com colunas notif falha, o job deve:
        - logar um warning
        - usar preferências padrão para os usuários
        - retornar resumo válido sem lançar exceção
        """
        now = datetime.now(timezone.utc)
        today = now.date()
        tomorrow = today + timedelta(days=1)

        upcoming_row = _make_row(
            numero="2024/UP1", objeto="Obras de pavimentação",
            orgao_nome="Prefeitura RJ", uf="RJ",
            data_abertura=datetime.combine(tomorrow, datetime.min.time()),
        )

        missing_col_exc = Exception("column u.notif_email does not exist")
        fav_row = _make_row(
            user_id=30, licitacao_id="2024/UP1",
            email="fav@example.com", nome="Favorita Teste",
        )

        pool = _make_pool(
            fetch_side_effects=[
                [upcoming_row],   # licitações upcoming
                missing_col_exc,  # favoritos com notif colunas → falha
                [fav_row],        # fallback favoritos sem notif colunas
                [],               # dedup already_sent
            ]
        )

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_SERVICE_MODULE}.send", AsyncMock()),
            patch(f"{NOTIF_SERVICE_MODULE}.send_document_expiration", AsyncMock()),
            caplog.at_level(logging.WARNING, logger="licitaim.monitor_worker"),
        ):
            from app.services.monitor_worker import check_upcoming_tenders
            result = await check_upcoming_tenders()

        assert "tenders_checked" in result
        assert "notifications_sent" in result
        assert "notifications_skipped" in result

        warning_text = " ".join(caplog.messages)
        assert any(
            kw in warning_text.lower()
            for kw in ("notif", "padrão", "indispon", "default")
        ), f"Warning esperado sobre colunas de notificação. Mensagens: {caplog.messages}"

    @pytest.mark.asyncio
    async def test_sends_with_default_prefs_in_fallback(self):
        """
        No caminho de fallback, o usuário deve receber notificação com
        notif_email=True e notif_push=True (defaults).
        """
        now = datetime.now(timezone.utc)
        today = now.date()
        tomorrow = today + timedelta(days=1)

        upcoming_row = _make_row(
            numero="2024/UP2", objeto="Aquisição de computadores",
            orgao_nome="Estado de MG", uf="MG",
            data_abertura=datetime.combine(tomorrow, datetime.min.time()),
        )

        missing_col_exc = Exception("column u.notif_email does not exist")
        fav_row = _make_row(
            user_id=40, licitacao_id="2024/UP2",
            email="mg@example.com", nome="MG Teste",
        )

        pool = _make_pool(
            fetch_side_effects=[
                [upcoming_row],
                missing_col_exc,
                [fav_row],
                [],  # dedup
            ]
        )

        captured_users: list[dict] = []

        async def _fake_send(user, *, title, body, tipo, metadata, cta_url, cta_label):
            captured_users.append(dict(user))

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_SERVICE_MODULE}.send", side_effect=_fake_send),
            patch(f"{NOTIF_SERVICE_MODULE}.send_document_expiration", AsyncMock()),
        ):
            from app.services.monitor_worker import check_upcoming_tenders
            result = await check_upcoming_tenders()

        assert result["notifications_sent"] >= 1
        assert len(captured_users) >= 1

        u = captured_users[0]
        assert u["notif_email"]    is True
        assert u["notif_push"]     is True
        assert u["notif_whatsapp"] is False
        assert u["notif_telegram"] is False

    @pytest.mark.asyncio
    async def test_no_exception_raised_when_columns_missing(self):
        """check_upcoming_tenders não propaga exceção com colunas ausentes."""
        now = datetime.now(timezone.utc)
        today = now.date()

        upcoming_row = _make_row(
            numero="2024/UP3", objeto="Serviços de limpeza",
            orgao_nome="Câmara Municipal", uf="PR",
            data_abertura=datetime.combine(today + timedelta(days=1), datetime.min.time()),
        )

        missing_col_exc = Exception("column u.notif_push does not exist")
        fav_row = _make_row(
            user_id=50, licitacao_id="2024/UP3",
            email="pr@example.com", nome="PR Teste",
        )

        pool = _make_pool(
            fetch_side_effects=[
                [upcoming_row],
                missing_col_exc,
                [fav_row],
                [],
            ]
        )

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_SERVICE_MODULE}.send", AsyncMock()),
            patch(f"{NOTIF_SERVICE_MODULE}.send_document_expiration", AsyncMock()),
        ):
            from app.services.monitor_worker import check_upcoming_tenders
            result = await check_upcoming_tenders()

        assert isinstance(result, dict)
        assert "notifications_sent" in result


# ===========================================================================
# check_document_expirations
# ===========================================================================

class TestCheckDocumentExpirations:
    """Testa check_document_expirations com e sem colunas de notificação."""

    @pytest.mark.asyncio
    async def test_returns_valid_summary_when_no_certs(self):
        """Sem certidões para alertar retorna resumo zerado."""
        pool = _make_pool(fetch_side_effects=[[]])

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_SERVICE_MODULE}.send_document_expiration", AsyncMock()),
        ):
            from app.services.monitor_worker import check_document_expirations
            result = await check_document_expirations()

        assert "certidoes_checked" in result
        assert "alerts_sent" in result
        assert "alerts_skipped" in result
        assert result["certidoes_checked"] == 0

    @pytest.mark.asyncio
    async def test_falls_back_to_defaults_when_notif_columns_missing(self, caplog):
        """
        Quando a query de certidões com colunas notif falha, o job deve:
        - logar um warning
        - usar preferências padrão
        - retornar resumo válido sem lançar exceção
        """
        today = date.today()

        missing_col_exc = Exception("column u.notif_email does not exist")
        cert_row = _make_row(
            id=1, nome="Certidão FGTS", tipo="fgts",
            data_vencimento=today + timedelta(days=7),
            user_id=60, email="cert@example.com", user_nome="Cert Teste",
        )

        pool = _make_pool(
            fetch_side_effects=[
                missing_col_exc,  # query com notif colunas → falha
                [cert_row],       # fallback sem notif colunas
            ]
        )
        pool.fetchval = AsyncMock(return_value=None)  # sem dedup

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_SERVICE_MODULE}.send_document_expiration", AsyncMock()),
            caplog.at_level(logging.WARNING, logger="licitaim.monitor_worker"),
        ):
            from app.services.monitor_worker import check_document_expirations
            result = await check_document_expirations()

        assert "certidoes_checked" in result
        assert "alerts_sent" in result
        assert "alerts_skipped" in result

        warning_text = " ".join(caplog.messages)
        assert any(
            kw in warning_text.lower()
            for kw in ("notif", "padrão", "indispon", "default")
        ), f"Warning esperado sobre colunas de notificação. Mensagens: {caplog.messages}"

    @pytest.mark.asyncio
    async def test_sends_with_default_prefs_in_fallback(self):
        """
        No fallback, send_document_expiration deve ser chamado com
        notif_email=True e notif_push=True (defaults).
        """
        today = date.today()

        missing_col_exc = Exception("column u.notif_email does not exist")
        cert_row = _make_row(
            id=2, nome="Certidão Municipal", tipo="municipal",
            data_vencimento=today + timedelta(days=30),
            user_id=70, email="mun@example.com", user_nome="Mun Teste",
        )

        pool = _make_pool(
            fetch_side_effects=[missing_col_exc, [cert_row]]
        )
        pool.fetchval = AsyncMock(return_value=None)

        captured_users: list[dict] = []

        async def _fake_send_doc_exp(user, certidao, dias, *, ref_key):
            captured_users.append(dict(user))
            return True  # simula INSERT persistido com sucesso

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_SERVICE_MODULE}.send_document_expiration", side_effect=_fake_send_doc_exp),
        ):
            from app.services.monitor_worker import check_document_expirations
            result = await check_document_expirations()

        assert result["alerts_sent"] >= 1
        assert len(captured_users) >= 1

        u = captured_users[0]
        assert u["notif_email"]    is True
        assert u["notif_push"]     is True
        assert u["notif_whatsapp"] is False
        assert u["notif_telegram"] is False

    @pytest.mark.asyncio
    async def test_no_exception_raised_when_columns_missing(self):
        """check_document_expirations não propaga exceção com colunas ausentes."""
        missing_col_exc = Exception("column u.notif_telegram does not exist")
        pool = _make_pool(
            fetch_side_effects=[missing_col_exc, []]
        )

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_SERVICE_MODULE}.send_document_expiration", AsyncMock()),
        ):
            from app.services.monitor_worker import check_document_expirations
            result = await check_document_expirations()

        assert isinstance(result, dict)
        assert "certidoes_checked" in result


# ===========================================================================
# check_task_deadlines (task_alerts.py)
# ===========================================================================

class TestCheckTaskDeadlines:
    """
    Testa que check_task_deadlines retorna resumo válido mesmo quando operações
    de DB falham (dedup ou INSERT de alerta).
    """

    @pytest.mark.asyncio
    async def test_returns_valid_summary_when_no_tasks(self):
        """Sem tarefas para alertar retorna resumo zerado."""
        pool = _make_pool(fetch_side_effects=[[]])

        with patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)):
            from app.services.task_alerts import check_task_deadlines
            result = await check_task_deadlines()

        assert "tasks_checked"  in result
        assert "alerts_created" in result
        assert "alerts_skipped" in result
        assert result["tasks_checked"] == 0

    @pytest.mark.asyncio
    async def test_returns_valid_summary_with_tasks_due(self):
        """Com tarefas a vencer, retorna resumo com contagens corretas."""
        today = date.today()

        task_row = _make_row(
            tarefa_id=1, gerenciamento_id=100,
            tarefa_titulo="Enviar documentação",
            prazo=today + timedelta(days=1),
            user_id=80,
            licitacao_objeto="Obra de reforma",
            licitacao_numero="2024/T1",
        )

        pool = _make_pool(fetch_side_effects=[[task_row]])
        pool.fetchval = AsyncMock(return_value=None)  # sem dedup

        with patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)):
            from app.services.task_alerts import check_task_deadlines
            result = await check_task_deadlines()

        assert result["tasks_checked"]  == 1
        assert result["alerts_created"] >= 1
        assert result["alerts_skipped"] == 0

    @pytest.mark.asyncio
    async def test_continues_when_dedup_query_fails(self, caplog):
        """
        Se o fetchval de deduplicação falhar, o job loga warning e prossegue
        criando o alerta mesmo assim (sem dedup).
        """
        today = date.today()

        task_row = _make_row(
            tarefa_id=2, gerenciamento_id=200,
            tarefa_titulo="Assinar contrato",
            prazo=today,
            user_id=90,
            licitacao_objeto="Serviços de TI",
            licitacao_numero="2024/T2",
        )

        pool = _make_pool(fetch_side_effects=[[task_row]])
        pool.fetchval = AsyncMock(side_effect=Exception("alertas table missing"))

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)),
            caplog.at_level(logging.WARNING, logger="licitaim.task_alerts"),
        ):
            from app.services.task_alerts import check_task_deadlines
            result = await check_task_deadlines()

        assert isinstance(result, dict)
        assert "tasks_checked" in result

        warning_text = " ".join(caplog.messages)
        assert any(
            kw in warning_text.lower()
            for kw in ("dedup", "deduplicação", "erro", "error")
        ), f"Warning de dedup esperado. Mensagens: {caplog.messages}"

    @pytest.mark.asyncio
    async def test_continues_when_insert_alerta_fails(self, caplog):
        """
        Se o INSERT em alertas falhar, o job loga warning e continua
        sem propagar a exceção.
        """
        today = date.today()

        task_row = _make_row(
            tarefa_id=3, gerenciamento_id=300,
            tarefa_titulo="Publicar edital",
            prazo=today + timedelta(days=3),
            user_id=100,
            licitacao_objeto="Material escolar",
            licitacao_numero="2024/T3",
        )

        pool = _make_pool(fetch_side_effects=[[task_row]])
        pool.fetchval = AsyncMock(return_value=None)
        # Primeira execute (INSERT alertas) falha; segunda (job_runs) ok
        pool.execute = AsyncMock(
            side_effect=[Exception("INSERT failed"), "OK"]
        )

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)),
            caplog.at_level(logging.WARNING, logger="licitaim.task_alerts"),
        ):
            from app.services.task_alerts import check_task_deadlines
            result = await check_task_deadlines()

        assert isinstance(result, dict)
        assert result["alerts_created"] == 0  # INSERT falhou
        warning_text = " ".join(caplog.messages)
        assert any(
            kw in warning_text.lower()
            for kw in ("erro", "alerta", "error")
        ), f"Warning de INSERT esperado. Mensagens: {caplog.messages}"

    @pytest.mark.asyncio
    async def test_skips_already_alerted_tasks(self):
        """Tarefas com alerta recente (dedup) são ignoradas."""
        today = date.today()

        task_row = _make_row(
            tarefa_id=4, gerenciamento_id=400,
            tarefa_titulo="Revisar proposta",
            prazo=today + timedelta(days=7),
            user_id=110,
            licitacao_objeto="Obras civis",
            licitacao_numero="2024/T4",
        )

        pool = _make_pool(fetch_side_effects=[[task_row]])
        pool.fetchval = AsyncMock(return_value=99)  # alerta já existe (id=99)

        with patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)):
            from app.services.task_alerts import check_task_deadlines
            result = await check_task_deadlines()

        assert result["tasks_checked"]  == 1
        assert result["alerts_created"] == 0
        assert result["alerts_skipped"] == 1


# ===========================================================================
# INSERT failures on the `alertas` table (schema drift)
# ===========================================================================

def _make_user_row(**extra) -> dict:
    """Linha de usuário completa com colunas notif (sem fallback necessário)."""
    defaults = dict(
        notif_email=True, notif_push=True,
        notif_whatsapp=False, notif_telegram=False,
        telegram_chat_id=None, phone=None,
    )
    return _make_row(**{**defaults, **extra})


def _make_failing_notif_pool(exc_msg: str = "column monitoramento_id does not exist") -> MagicMock:
    """
    Pool que simula falha no INSERT da tabela `alertas` dentro das funções do
    notification_service.  pool.acquire() retorna um context-manager com uma
    conexão cujo execute() sempre levanta exceção.
    """
    conn = MagicMock()
    conn.execute = AsyncMock(side_effect=Exception(exc_msg))

    tx_cm = MagicMock()
    tx_cm.__aenter__ = AsyncMock(return_value=conn)
    tx_cm.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx_cm)

    acq_cm = MagicMock()
    acq_cm.__aenter__ = AsyncMock(return_value=conn)
    acq_cm.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acq_cm)
    pool.execute = AsyncMock(side_effect=Exception(exc_msg))
    return pool


def _make_ok_notif_pool() -> MagicMock:
    """
    Pool que simula sucesso no INSERT da tabela `alertas` dentro das funções do
    notification_service.
    """
    conn = MagicMock()
    conn.execute = AsyncMock(return_value="OK")

    tx_cm = MagicMock()
    tx_cm.__aenter__ = AsyncMock(return_value=conn)
    tx_cm.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx_cm)

    acq_cm = MagicMock()
    acq_cm.__aenter__ = AsyncMock(return_value=conn)
    acq_cm.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acq_cm)
    pool.execute = AsyncMock(return_value="OK")
    return pool


class TestAlertasInsertFailures:
    """
    Confirma que falhas no INSERT da tabela `alertas` (ex.: coluna ausente por
    schema drift) NÃO produzem contagens positivas enganosas e que o job
    continua processando os registros seguintes.

    Estes testes exercem as funções REAIS de notification_service
    (send_monitor_match, send_document_expiration) — sem mocká-las
    completamente — e injetam um pool que falha na execução do INSERT para
    simular a falha de schema drift no caminho de persistência.

    Cada sub-grupo cobre um dos três jobs do monitor_worker.
    """

    # ── check_all_monitors ─────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_all_monitors_does_not_count_when_alertas_insert_fails(self, caplog):
        """
        Quando o INSERT em alertas falha dentro de send_monitor_match (ex.:
        coluna monitoramento_id ausente), send_monitor_match retorna False e o
        job não contabiliza o match.
        Um warning é registrado dentro de send_monitor_match.
        """
        now = datetime.now(timezone.utc)

        monitor_row = _make_user_row(
            id=101, user_id=1001, nome="Monitor INSERT-fail",
            palavras_chave='["limpeza"]', modalidades="[]", ufs='["SP"]',
            valor_min=None, valor_max=None,
            last_checked_at=now - timedelta(hours=1),
            email="fail@example.com", user_nome="Fail User",
        )
        tender_row = _make_row(
            numero="2024/M1", objeto="Serviços de limpeza",
            orgao_nome="Prefeitura SP", uf="SP", modalidade="pregao",
            valor_estimado=100000.0,
            data_abertura=now + timedelta(days=5),
            data_publicacao=now - timedelta(hours=30),
        )

        # main_pool: atende às queries do monitor_worker (monitors, search_cache, dedup alertas)
        main_pool = _make_pool(
            fetch_side_effects=[
                [monitor_row],  # monitors query (_fetch_with_notif_fallback)
                [tender_row],   # _search_cache
                [],             # alertas dedup fetch
            ]
        )
        # notif_pool: usado por send_monitor_match; conn.execute lança → INSERT falha
        notif_pool = _make_failing_notif_pool("column monitoramento_id does not exist")

        # get_pool() é chamado 1× pelo monitor_worker, 1× pelo send_monitor_match
        get_pool_seq = [main_pool, notif_pool]

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(side_effect=get_pool_seq)),
            patch(f"{NOTIF_SERVICE_MODULE}.send", AsyncMock()),
            caplog.at_level(logging.WARNING, logger="licitaim.notifications"),
        ):
            from app.services.monitor_worker import check_all_monitors
            result = await check_all_monitors()

        assert result["monitors_checked"] == 1
        assert result["matches_found"] == 0, (
            f"matches_found deve ser 0 quando alertas INSERT falha; "
            f"got {result['matches_found']}"
        )
        warning_text = " ".join(caplog.messages)
        assert any(
            kw in warning_text.lower()
            for kw in ("monitoramento_id", "alerta db", "db error", "error")
        ), f"Warning de send_monitor_match esperado. Mensagens: {caplog.messages}"

    @pytest.mark.asyncio
    async def test_all_monitors_continues_to_next_monitor_after_insert_failure(self, caplog):
        """
        Quando o INSERT falha para o monitor 1, send_monitor_match retorna False
        e o job continua para o monitor 2, que tem INSERT bem-sucedido e conta 1 match.
        """
        now = datetime.now(timezone.utc)

        def _mon(id_, user_id, email):
            return _make_user_row(
                id=id_, user_id=user_id, nome=f"Monitor {id_}",
                palavras_chave='["obra"]', modalidades="[]", ufs='["MG"]',
                valor_min=None, valor_max=None,
                last_checked_at=now - timedelta(hours=1),
                email=email, user_nome=f"User {id_}",
            )

        tender_row = _make_row(
            numero="2024/M2", objeto="Obra de reforma",
            orgao_nome="Estado MG", uf="MG", modalidade="concorrencia",
            valor_estimado=500000.0,
            data_abertura=now + timedelta(days=10),
            data_publicacao=now - timedelta(hours=20),
        )

        main_pool = _make_pool(
            fetch_side_effects=[
                [_mon(1, 10, "a@mg.com"), _mon(2, 20, "b@mg.com")],  # monitors
                [tender_row],  # _search_cache monitor 1
                [],            # alertas dedup monitor 1
                [tender_row],  # _search_cache monitor 2
                [],            # alertas dedup monitor 2
            ]
        )
        failing_pool = _make_failing_notif_pool("column monitoramento_id does not exist")
        ok_pool      = _make_ok_notif_pool()

        # get_pool calls: 1 (monitor_worker) + 1 (send_monitor_match m1) + 1 (send_monitor_match m2)
        get_pool_seq = [main_pool, failing_pool, ok_pool]

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(side_effect=get_pool_seq)),
            patch(f"{NOTIF_SERVICE_MODULE}.send", AsyncMock()),
        ):
            from app.services.monitor_worker import check_all_monitors
            result = await check_all_monitors()

        assert result["monitors_checked"] == 2
        # monitor 1: INSERT falhou → persisted=False → não conta
        # monitor 2: INSERT ok → persisted=True → conta 1
        assert result["matches_found"] == 1, (
            f"Expected 1 match (monitor 2 ok); got {result['matches_found']}"
        )

    # ── check_upcoming_tenders ────────────────────────────────────────────
    # O INSERT em alertas é executado diretamente via pool.execute neste job,
    # por isso o pool principal é suficiente para simular a falha.
    # Com insert_ok=False, a notificação ainda é entregue via send() mas NÃO
    # é contada em notifications_sent.

    @pytest.mark.asyncio
    async def test_upcoming_tenders_count_zero_when_alertas_insert_fails(self, caplog):
        """
        Quando o INSERT em alertas falha, notifications_sent deve ser 0 (a
        notificação ainda é enviada via canais, mas não é contada pois não
        está persistida para deduplicação futura).
        """
        now = datetime.now(timezone.utc)
        today = now.date()
        tomorrow = today + timedelta(days=1)

        upcoming_row = _make_row(
            numero="2024/UP10", objeto="Compra de equipamentos",
            orgao_nome="Estado CE", uf="CE",
            data_abertura=datetime.combine(tomorrow, datetime.min.time()),
        )
        fav_row = _make_user_row(
            user_id=301, licitacao_id="2024/UP10",
            email="ce@example.com", nome="CE Teste",
        )

        pool = _make_pool(
            fetch_side_effects=[
                [upcoming_row],  # licitações upcoming
                [fav_row],       # favoritos (full query — notif cols ok)
                [],              # already_sent dedup
            ]
        )
        # INSERT em alertas falha
        pool.execute = AsyncMock(side_effect=Exception("column lido does not exist"))

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_SERVICE_MODULE}.send", AsyncMock()),
            patch(f"{NOTIF_SERVICE_MODULE}.send_document_expiration", AsyncMock()),
            caplog.at_level(logging.WARNING, logger="licitaim.monitor_worker"),
        ):
            from app.services.monitor_worker import check_upcoming_tenders
            result = await check_upcoming_tenders()

        assert result["notifications_sent"] == 0, (
            f"Expected notifications_sent=0 when alertas INSERT fails; "
            f"got {result['notifications_sent']}"
        )
        assert any(
            kw in m.lower()
            for m in caplog.messages
            for kw in ("persistir", "erro", "error", "lido")
        ), f"Warning sobre falha no INSERT esperado. Mensagens: {caplog.messages}"

    @pytest.mark.asyncio
    async def test_upcoming_tenders_still_delivers_and_counts_when_second_insert_succeeds(self, caplog):
        """
        Quando o INSERT falha para fav1 e tem êxito para fav2:
        - send() é chamado para AMBOS (notificação entregue independente da persistência)
        - notifications_sent = 1 (apenas fav2 foi persistido com sucesso)
        O job continua processando após a falha do primeiro.
        """
        now = datetime.now(timezone.utc)
        today = now.date()
        tomorrow = today + timedelta(days=1)

        upcoming1 = _make_row(
            numero="2024/UP11", objeto="Obra de ponte",
            orgao_nome="Estado RS", uf="RS",
            data_abertura=datetime.combine(tomorrow, datetime.min.time()),
        )
        upcoming2 = _make_row(
            numero="2024/UP12", objeto="Compra de mobiliário",
            orgao_nome="Estado RS", uf="RS",
            data_abertura=datetime.combine(tomorrow, datetime.min.time()),
        )
        fav1 = _make_user_row(
            user_id=302, licitacao_id="2024/UP11",
            email="rs1@example.com", nome="RS Teste 1",
        )
        fav2 = _make_user_row(
            user_id=303, licitacao_id="2024/UP12",
            email="rs2@example.com", nome="RS Teste 2",
        )

        pool = _make_pool(
            fetch_side_effects=[
                [upcoming1, upcoming2],  # licitações upcoming
                [fav1, fav2],            # favoritos
                [],                      # already_sent dedup
            ]
        )
        # INSERT fav1 → falha; INSERT fav2 → ok
        pool.execute = AsyncMock(
            side_effect=[Exception("column monitoramento_id does not exist"), "OK"]
        )

        send_calls: list = []

        async def _fake_send(user, *, title, body, tipo, metadata, cta_url, cta_label):
            send_calls.append(user["id"])

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(return_value=pool)),
            patch(f"{NOTIF_SERVICE_MODULE}.send", side_effect=_fake_send),
            patch(f"{NOTIF_SERVICE_MODULE}.send_document_expiration", AsyncMock()),
            caplog.at_level(logging.WARNING, logger="licitaim.monitor_worker"),
        ):
            from app.services.monitor_worker import check_upcoming_tenders
            result = await check_upcoming_tenders()

        # Apenas fav2 persistido → notifications_sent = 1
        assert result["notifications_sent"] == 1, (
            f"Expected 1 (fav2 ok); got {result['notifications_sent']}"
        )
        # send() é chamado para AMBOS os favoritos (entrega sempre ocorre)
        assert len(send_calls) == 2, (
            f"send() deve ser chamado para ambos os favs; got {len(send_calls)} calls"
        )
        user_ids_notified = {str(uid) for uid in send_calls}
        assert str(fav1["user_id"]) in user_ids_notified, "fav1 deve ter recebido notificação via canais"
        assert str(fav2["user_id"]) in user_ids_notified, "fav2 deve ter recebido notificação via canais"

    # ── check_document_expirations ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_document_expirations_count_zero_when_alertas_insert_fails(self, caplog):
        """
        Quando o INSERT em alertas falha dentro de send_document_expiration
        (ex.: coluna link ausente), a função retorna False e alerts_sent fica 0.
        Um warning é registrado dentro de send_document_expiration.
        """
        today = date.today()

        cert_row = _make_user_row(
            id=201, nome="Certidão Trabalhista", tipo="trabalhista",
            data_vencimento=today + timedelta(days=7),
            user_id=601, email="trab@example.com", user_nome="Trab Teste",
        )

        # main_pool: atende às queries do monitor_worker (certs fetch, dedup fetchval)
        main_pool = _make_pool(fetch_side_effects=[[cert_row]])
        main_pool.fetchval = AsyncMock(return_value=None)  # sem dedup
        # notif_pool: usado por send_document_expiration; pool.execute lança → INSERT falha
        notif_pool = _make_failing_notif_pool("column link does not exist")

        # get_pool calls: 1 (monitor_worker) + 1 (send_document_expiration)
        get_pool_seq = [main_pool, notif_pool]

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(side_effect=get_pool_seq)),
            patch(f"{NOTIF_SERVICE_MODULE}.send", AsyncMock()),
            caplog.at_level(logging.WARNING, logger="licitaim.notifications"),
        ):
            from app.services.monitor_worker import check_document_expirations
            result = await check_document_expirations()

        assert result["alerts_sent"] == 0, (
            f"Expected alerts_sent=0 when alertas INSERT fails; got {result['alerts_sent']}"
        )
        warning_text = " ".join(caplog.messages)
        assert any(
            kw in warning_text.lower()
            for kw in ("link", "db error", "error")
        ), f"Warning de send_document_expiration esperado. Mensagens: {caplog.messages}"

    @pytest.mark.asyncio
    async def test_document_expirations_continues_after_first_cert_insert_failure(self):
        """
        Quando o INSERT falha para cert 1 e tem êxito para cert 2,
        alerts_sent = 1 e o job ainda envia notificação para cert 2.
        """
        today = date.today()

        cert1 = _make_user_row(
            id=202, nome="Certidão Federal", tipo="federal",
            data_vencimento=today + timedelta(days=7),
            user_id=701, email="fed@example.com", user_nome="Fed Teste",
        )
        cert2 = _make_user_row(
            id=203, nome="Certidão Estadual", tipo="estadual",
            data_vencimento=today + timedelta(days=30),
            user_id=702, email="est@example.com", user_nome="Est Teste",
        )

        main_pool = _make_pool(fetch_side_effects=[[cert1, cert2]])
        main_pool.fetchval = AsyncMock(return_value=None)  # sem dedup para ambas

        failing_pool = _make_failing_notif_pool("column link does not exist")
        ok_pool      = _make_ok_notif_pool()

        # get_pool calls: 1 (monitor_worker) + 1 (send_doc_exp cert1) + 1 (send_doc_exp cert2)
        # + 1 (job_runs INSERT at the end, which uses the already-fetched main_pool — no extra get_pool)
        # Actually job_runs uses main_pool.execute (via the pool variable in check_document_expirations)
        get_pool_seq = [main_pool, failing_pool, ok_pool]

        with (
            patch(f"{DB_SESSION_MODULE}.get_pool", AsyncMock(side_effect=get_pool_seq)),
            patch(f"{NOTIF_SERVICE_MODULE}.send", AsyncMock()),
        ):
            from app.services.monitor_worker import check_document_expirations
            result = await check_document_expirations()

        assert result["certidoes_checked"] == 2
        assert result["alerts_sent"] == 1, (
            f"Expected 1 (cert1 INSERT failed → False, cert2 ok → True); "
            f"got {result['alerts_sent']}"
        )
