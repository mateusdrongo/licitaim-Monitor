"""
test_collector_alerts.py

Testa o comportamento de "at-most-once-per-outage" de check_collector_staleness():

1. Com timestamp antigo (stale), chama o job duas vezes:
   - 1ª chamada → alerta enviado, is_stale_alerted salvo como TRUE.
   - 2ª chamada → nenhum alerta adicional (já estava alerted).

2. Com timestamp fresco (recovered), chama o job:
   - 1ª chamada → notificação de recuperação enviada, is_stale_alerted salvo como FALSE.
   - 2ª chamada → nenhuma notificação adicional (já estava recovered).

O pool de banco é substituído por um mock com estado em memória para que as
chamadas consecutivas observem o mesmo estado persistido, exatamente como
fariam com um banco real.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# Módulos a serem patchados
DB_SESSION_MODULE  = "app.db.session"
# notification_service.send é importado lazily dentro de check_collector_staleness;
# patchamos diretamente no módulo original.
NOTIF_SEND_TARGET  = "app.services.notification_service.send"
ADMIN_EMAILS_TARGET = "app.services.collector_alerts._admin_emails"


# ── Mock de pool com estado em memória ───────────────────────────────────────

class _MockRecord(dict):
    """Comporta-se como asyncpg.Record: acesso por chave e iteração."""
    pass


class _StatefulPool:
    """
    Pool falso que mantém o estado de collector_alert_state em memória.

    Parâmetros
    ----------
    stale:
        Se True, retorna timestamp antigo (>8h) para collector_status,
        fazendo _compute_is_stale() retornar True.
        Se False, retorna timestamp recente (agora).
    admins:
        Lista de dicts devolvida quando a query é sobre `users`.
    """

    def __init__(self, *, stale: bool, admins: list[dict] | None = None):
        self.stale = stale
        self.admins = admins or [{"id": "admin1", "nome": "Admin Teste", "email": "admin@test.com"}]
        # Estado persistido entre chamadas — espelha a linha id=1 da tabela
        self._alert_state: dict = {
            "id": 1,
            "is_stale_alerted": False,
            "alerted_at": None,
            "recovered_at": None,
        }
        # Rastreia quais queries de execute() foram chamadas
        self.execute_calls: list[str] = []

    def _collector_status_rows(self) -> list[_MockRecord]:
        now = datetime.now(timezone.utc)
        ts = now - timedelta(hours=10) if self.stale else now
        return [_MockRecord(portal="global", last_run=ts, interval_hours=4)]

    async def fetch(self, query: str, *args):
        q = query.strip().lower()
        if "collector_status" in q:
            return self._collector_status_rows()
        if "users" in q:
            return [_MockRecord(**a) for a in self.admins]
        return []

    async def fetchrow(self, query: str, *args):
        q = query.strip().lower()
        if "collector_alert_state" in q:
            return _MockRecord(**self._alert_state)
        return None

    async def execute(self, query: str, *args):
        self.execute_calls.append(query.strip())
        q = query.lower()
        if "is_stale_alerted = true" in q:
            self._alert_state["is_stale_alerted"] = True
        elif "is_stale_alerted = false" in q:
            self._alert_state["is_stale_alerted"] = False


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def stale_pool() -> _StatefulPool:
    """Pool que reporta collector como parado (timestamp antigo)."""
    return _StatefulPool(stale=True)


@pytest.fixture()
def fresh_pool() -> _StatefulPool:
    """Pool que reporta collector como saudável (timestamp recente)."""
    return _StatefulPool(stale=False)


# ── Testes principais ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stale_alert_fires_only_once(stale_pool):
    """
    Dado um collector parado, o alerta deve ser enviado apenas na primeira
    chamada. A segunda chamada, ainda com collector parado, não deve reenviar.
    """
    # Força importação do módulo para que o patch funcione
    import app.services.notification_service  # noqa: F401
    from app.services.collector_alerts import check_collector_staleness

    with patch(DB_SESSION_MODULE + ".get_pool", new=AsyncMock(return_value=stale_pool)), \
         patch(NOTIF_SEND_TARGET, new_callable=AsyncMock) as mock_send, \
         patch(ADMIN_EMAILS_TARGET, return_value={"admin@test.com"}):

        # ── 1ª chamada: deve alertar ──────────────────────────────────────────
        result1 = await check_collector_staleness()

        assert result1["is_stale"] is True
        assert result1["alerted"] is True
        assert result1["recovered"] is False
        assert result1["admins_notified"] == 1

        # Estado deve ter sido persistido como alerted=True
        assert stale_pool._alert_state["is_stale_alerted"] is True

        send_count_after_first = mock_send.call_count
        assert send_count_after_first == 1

        # ── 2ª chamada: collector ainda parado — NÃO deve reenviar ───────────
        result2 = await check_collector_staleness()

        assert result2["is_stale"] is True
        assert result2["alerted"] is False, "Não deve alertar de novo no mesmo ciclo"
        assert result2["recovered"] is False
        assert result2["admins_notified"] == 0

        # send() não deve ter sido chamado novamente
        assert mock_send.call_count == send_count_after_first, (
            "notification_service.send foi chamado mais de uma vez durante o mesmo outage"
        )


@pytest.mark.asyncio
async def test_recovery_alert_fires_and_resets_state(fresh_pool):
    """
    Após o collector se recuperar (is_stale_alerted=True → pool fresco),
    uma notificação de recuperação deve ser enviada e o estado deve voltar
    a is_stale_alerted=False.
    """
    import app.services.notification_service  # noqa: F401
    from app.services.collector_alerts import check_collector_staleness

    # Simula que o alerta de inatividade já foi enviado anteriormente
    fresh_pool._alert_state["is_stale_alerted"] = True

    with patch(DB_SESSION_MODULE + ".get_pool", new=AsyncMock(return_value=fresh_pool)), \
         patch(NOTIF_SEND_TARGET, new_callable=AsyncMock) as mock_send, \
         patch(ADMIN_EMAILS_TARGET, return_value={"admin@test.com"}):

        result = await check_collector_staleness()

        assert result["is_stale"] is False
        assert result["alerted"] is False
        assert result["recovered"] is True
        assert result["admins_notified"] == 1

        # Estado deve ter sido resetado para False
        assert fresh_pool._alert_state["is_stale_alerted"] is False

        assert mock_send.call_count == 1
        # Verifica que o evento correto foi passado nos metadados
        _, kwargs = mock_send.call_args
        assert kwargs.get("metadata", {}).get("event") == "collector_recovered"


@pytest.mark.asyncio
async def test_recovery_alert_fires_only_once(fresh_pool):
    """
    Após a recuperação ser notificada, uma segunda chamada com collector
    saudável NÃO deve reenviar a notificação de recuperação.
    """
    import app.services.notification_service  # noqa: F401
    from app.services.collector_alerts import check_collector_staleness

    # Começa "already alerted" para que a 1ª chamada dispare a recuperação
    fresh_pool._alert_state["is_stale_alerted"] = True

    with patch(DB_SESSION_MODULE + ".get_pool", new=AsyncMock(return_value=fresh_pool)), \
         patch(NOTIF_SEND_TARGET, new_callable=AsyncMock) as mock_send, \
         patch(ADMIN_EMAILS_TARGET, return_value={"admin@test.com"}):

        # 1ª chamada — deve disparar recuperação
        result1 = await check_collector_staleness()
        assert result1["recovered"] is True
        assert mock_send.call_count == 1

        # 2ª chamada — is_stale_alerted agora é False; não deve reenviar
        result2 = await check_collector_staleness()
        assert result2["recovered"] is False
        assert result2["alerted"] is False
        assert result2["admins_notified"] == 0

        # send() NÃO deve ter sido chamado uma segunda vez
        assert mock_send.call_count == 1, (
            "notification_service.send disparou mais de uma vez após a recuperação"
        )


@pytest.mark.asyncio
async def test_no_admins_still_marks_state(stale_pool):
    """
    Quando ADMIN_EMAILS não está configurado (sem admins), o job ainda deve
    persistir is_stale_alerted=True para não logar o warning a cada ciclo.
    """
    import app.services.notification_service  # noqa: F401
    from app.services.collector_alerts import check_collector_staleness

    # Pool sem admins cadastrados
    stale_pool.admins = []

    with patch(DB_SESSION_MODULE + ".get_pool", new=AsyncMock(return_value=stale_pool)), \
         patch(NOTIF_SEND_TARGET, new_callable=AsyncMock) as mock_send, \
         patch(ADMIN_EMAILS_TARGET, return_value=set()):

        result = await check_collector_staleness()

        assert result["alerted"] is True           # job processou o evento
        assert result["admins_notified"] == 0      # nenhum admin para notificar
        assert stale_pool._alert_state["is_stale_alerted"] is True

        # send() não deve ter sido chamado
        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_full_lifecycle(stale_pool, fresh_pool):
    """
    Ciclo completo: stale → alerta → stale de novo (sem duplicata) →
    recuperação → recuperação de novo (sem duplicata).
    """
    import app.services.notification_service  # noqa: F401
    from app.services.collector_alerts import check_collector_staleness

    # ── Fase 1: stale ──────────────────────────────────────────────────────────
    with patch(DB_SESSION_MODULE + ".get_pool", new=AsyncMock(return_value=stale_pool)), \
         patch(NOTIF_SEND_TARGET, new_callable=AsyncMock) as mock_send, \
         patch(ADMIN_EMAILS_TARGET, return_value={"admin@test.com"}):

        r1 = await check_collector_staleness()
        assert r1["alerted"] is True

        r2 = await check_collector_staleness()
        assert r2["alerted"] is False            # sem duplicata

        assert mock_send.call_count == 1         # apenas 1 envio no total

    # ── Fase 2: recuperação — copia estado para o fresh_pool ──────────────────
    fresh_pool._alert_state["is_stale_alerted"] = stale_pool._alert_state["is_stale_alerted"]

    with patch(DB_SESSION_MODULE + ".get_pool", new=AsyncMock(return_value=fresh_pool)), \
         patch(NOTIF_SEND_TARGET, new_callable=AsyncMock) as mock_send, \
         patch(ADMIN_EMAILS_TARGET, return_value={"admin@test.com"}):

        r3 = await check_collector_staleness()
        assert r3["recovered"] is True

        r4 = await check_collector_staleness()
        assert r4["recovered"] is False          # sem duplicata de recuperação

        assert mock_send.call_count == 1         # apenas 1 envio de recuperação
