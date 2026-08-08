"""
collector_alerts.py — Job periódico que monitora a saúde do collector
                       e alerta admins quando ele fica parado por muito tempo.

Comportamento:
  • Verifica o status do collector a cada 30 min (agendado pelo cache_scheduler).
  • Quando is_stale flipa para True: envia alerta a todos os admins (push + email).
  • Quando o collector se recupera: envia notificação de recuperação.
  • Garante "at most once per outage": usa a tabela collector_alert_state (row id=1)
    como estado persistente, evitando re-alertas em cada ciclo de verificação.

Configuração:
  • ADMIN_EMAILS (CSV) — mesma variável usada por app.core.admin.
  • Se não configurado, nenhuma notificação é enviada (a variável é obrigatória
    para qualquer rota administrativa, então sua ausência indica ambiente dev/sem-admin).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger("licitaim.collector_alerts")

# Limiar de inatividade em horas — idêntico ao de collector.py
_STALE_THRESHOLD_HOURS = 8
_DEFAULT_INTERVAL_HOURS = 4


def _admin_emails() -> set[str]:
    """Lê ADMIN_EMAILS e retorna conjunto normalizado de e-mails."""
    raw = os.getenv("ADMIN_EMAILS", "").strip()
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


async def _fetch_admin_users(pool) -> list[dict]:
    """Retorna lista de dicts {id, nome, email} para cada admin configurado."""
    emails = _admin_emails()
    if not emails:
        return []
    rows = await pool.fetch(
        "SELECT id, nome, email FROM users WHERE LOWER(email) = ANY($1)",
        list(emails),
    )
    return [dict(r) for r in rows]


async def _compute_is_stale(pool) -> bool:
    """
    Replica a lógica de is_stale de collector.py consultando diretamente o banco,
    sem passar pelo endpoint HTTP (mais confiável dentro do mesmo processo).
    """
    try:
        rows = await pool.fetch(
            "SELECT portal, last_run, interval_hours FROM collector_status ORDER BY portal"
        )
    except Exception as exc:
        logger.warning("collector_alerts: falha ao ler collector_status: %s", exc)
        return True  # sem dados → considera parado

    if not rows:
        return True

    now = datetime.now(timezone.utc)

    # Procura linha global ou agrega o timestamp mais recente entre portais
    global_last_run: datetime | None = None
    for row in rows:
        ts = row["last_run"]
        if ts and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if row["portal"] == "global":
            global_last_run = ts
            break
        if ts and (global_last_run is None or ts > global_last_run):
            global_last_run = ts

    if global_last_run is None:
        return True

    hours_ago = (now - global_last_run).total_seconds() / 3600
    return hours_ago > _STALE_THRESHOLD_HOURS


async def _get_alert_state(pool) -> dict:
    """Lê o único row da tabela collector_alert_state."""
    row = await pool.fetchrow("SELECT * FROM collector_alert_state WHERE id = 1")
    if row is None:
        # Não deveria acontecer após a migration, mas protege contra race conditions
        await pool.execute(
            "INSERT INTO collector_alert_state (id, is_stale_alerted) VALUES (1, FALSE)"
            " ON CONFLICT (id) DO NOTHING"
        )
        return {"is_stale_alerted": False, "alerted_at": None, "recovered_at": None}
    return dict(row)


async def check_collector_staleness() -> dict:
    """
    Job principal: verifica saúde do collector e dispara alertas quando necessário.

    Retorna resumo: {is_stale, alerted, recovered, admins_notified}.
    """
    from ..db.session import get_pool
    from . import notification_service

    pool = await get_pool()

    is_stale = await _compute_is_stale(pool)
    state = await _get_alert_state(pool)
    already_alerted: bool = state["is_stale_alerted"]

    alerted = False
    recovered = False
    admins_notified = 0

    if is_stale and not already_alerted:
        # ── Novo evento de inatividade ────────────────────────────────────────
        admins = await _fetch_admin_users(pool)
        if not admins:
            logger.warning(
                "collector_alerts: collector está parado mas ADMIN_EMAILS não está "
                "configurado — nenhum alerta enviado."
            )
        else:
            title = "🚨 Collector parado: dados desatualizados"
            body = (
                "O collector de licitações não executa há mais de "
                f"{_STALE_THRESHOLD_HOURS} horas. "
                "Os dados exibidos para os usuários podem estar desatualizados. "
                "Verifique se o serviço coletor está em execução."
            )
            for admin in admins:
                try:
                    await notification_service.send(
                        user=admin,
                        title=title,
                        body=body,
                        channels=["push", "email"],
                        tipo="alerta_collector",
                        metadata={"event": "collector_stale"},
                        cta_url="/admin",
                        cta_label="Verificar sistema",
                    )
                    admins_notified += 1
                except Exception as exc:
                    logger.warning(
                        "collector_alerts: falha ao notificar admin %s: %s",
                        admin.get("email"), exc,
                    )

        # Persiste estado — mesmo sem admins configurados, marca alerted para não
        # logar o warning a cada ciclo
        await pool.execute(
            """
            UPDATE collector_alert_state
               SET is_stale_alerted = TRUE,
                   alerted_at       = NOW()
             WHERE id = 1
            """
        )
        alerted = True
        logger.info(
            "collector_alerts: alerta de inatividade enviado para %d admin(s).",
            admins_notified,
        )

    elif not is_stale and already_alerted:
        # ── Collector se recuperou ────────────────────────────────────────────
        admins = await _fetch_admin_users(pool)
        if admins:
            title = "✅ Collector recuperado"
            body = (
                "O collector de licitações voltou a funcionar normalmente. "
                "Os dados estão sendo atualizados novamente."
            )
            for admin in admins:
                try:
                    await notification_service.send(
                        user=admin,
                        title=title,
                        body=body,
                        channels=["push", "email"],
                        tipo="alerta_collector",
                        metadata={"event": "collector_recovered"},
                        cta_url="/admin",
                        cta_label="Ver status",
                    )
                    admins_notified += 1
                except Exception as exc:
                    logger.warning(
                        "collector_alerts: falha ao notificar recuperação para admin %s: %s",
                        admin.get("email"), exc,
                    )

        await pool.execute(
            """
            UPDATE collector_alert_state
               SET is_stale_alerted = FALSE,
                   recovered_at     = NOW()
             WHERE id = 1
            """
        )
        recovered = True
        logger.info(
            "collector_alerts: notificação de recuperação enviada para %d admin(s).",
            admins_notified,
        )

    else:
        logger.debug(
            "collector_alerts: sem mudança de estado "
            "(is_stale=%s, already_alerted=%s).",
            is_stale, already_alerted,
        )

    return {
        "is_stale": is_stale,
        "alerted": alerted,
        "recovered": recovered,
        "admins_notified": admins_notified,
    }
