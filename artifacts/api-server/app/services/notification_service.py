"""
NotificationService — orquestra envio de notificações multi-canal.

Canais suportados: push (WS + DB), email, whatsapp, telegram.
As preferências do usuário controlam quais canais são usados.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("licitaim.notifications")

# Canais disponíveis
CHANNEL_PUSH      = "push"
CHANNEL_EMAIL     = "email"
CHANNEL_WHATSAPP  = "whatsapp"
CHANNEL_TELEGRAM  = "telegram"

ALL_CHANNELS = [CHANNEL_PUSH, CHANNEL_EMAIL, CHANNEL_WHATSAPP, CHANNEL_TELEGRAM]
DEFAULT_CHANNELS = [CHANNEL_PUSH, CHANNEL_EMAIL]


# ── Função principal ──────────────────────────────────────────────────────────

async def send(
    user: dict,
    title: str,
    body: str,
    channels: Optional[list[str]] = None,
    tipo: str = "info",
    metadata: Optional[dict] = None,
    cta_url: str = "",
    cta_label: str = "",
) -> dict[str, bool]:
    """
    Dispara notificação para o usuário nos canais especificados.
    Respeita as preferências de notificação do usuário.

    Returns: dict {channel: success}
    """
    user_id = str(user.get("id", ""))
    # When no explicit channel list is given, offer all channels and let
    # _resolve_channels filter down to what the user has actually enabled.
    active_channels = _resolve_channels(user, channels if channels is not None else ALL_CHANNELS)
    results: dict[str, bool] = {}

    for channel in active_channels:
        try:
            if channel == CHANNEL_PUSH:
                from .senders.push_sender import send_push
                results[channel] = await send_push(
                    user_id, title, body, tipo=tipo, metadata=metadata
                )

            elif channel == CHANNEL_EMAIL:
                from .senders.email_sender import send_email
                results[channel] = await send_email(
                    to=user.get("email", ""),
                    subject=title,
                    body_text=body,
                    cta_url=cta_url,
                    cta_label=cta_label,
                )

            elif channel == CHANNEL_WHATSAPP:
                phone = user.get("phone") or user.get("telefone", "")
                if phone:
                    from .senders.whatsapp_sender import send_whatsapp
                    results[channel] = await send_whatsapp(phone, f"*{title}*\n\n{body}")
                else:
                    results[channel] = False

            elif channel == CHANNEL_TELEGRAM:
                chat_id = user.get("telegram_chat_id", "")
                if chat_id:
                    from .senders.telegram_sender import send_telegram
                    results[channel] = await send_telegram(
                        chat_id, f"<b>{title}</b>\n\n{body}"
                    )
                else:
                    results[channel] = False

        except Exception as exc:
            logger.warning("send[%s] user=%s: %s", channel, user_id, exc)
            results[channel] = False

    logger.info(
        "NotificationService: user=%s title=%r channels=%s results=%s",
        user_id, title, active_channels, results,
    )
    return results


# ── Mensagens pré-formatadas ──────────────────────────────────────────────────

async def send_monitor_match(
    user: dict,
    monitor: dict,
    tender: dict,
    background_tasks=None,
) -> bool:
    """
    Notifica usuário sobre novo tender que fez match com um monitor.
    Também cria registro em `alertas`.

    Returns True se o alerta foi persistido com sucesso em `alertas`, False caso contrário.
    A notificação via canais (email, push, etc.) é sempre tentada, independente da persistência.
    """
    from ..db.session import get_pool

    monitor_name = monitor.get("nome", "")
    objeto = tender.get("objeto", tender.get("objetoCompra", ""))[:200]
    orgao  = tender.get("orgao", "")
    uf     = tender.get("uf", "")
    valor  = tender.get("valorEstimado") or tender.get("valor_estimado")

    valor_str = (
        f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if valor else "Não informado"
    )

    title = f"🔔 Novo match: {monitor_name}"
    body  = (
        f"Uma nova licitação foi encontrada para o monitor '{monitor_name}'.\n\n"
        f"Objeto: {objeto}\n"
        f"Órgão: {orgao} ({uf})\n"
        f"Valor estimado: {valor_str}"
    )

    tender_id  = tender.get("id") or tender.get("external_id", "")
    user_id    = str(user.get("id", ""))
    monitor_id = monitor.get("id")

    # Persiste alerta no banco (com monitoramento_id para FK correta)
    persisted = False
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """INSERT INTO alertas
                       (user_id, tipo, titulo, descricao, licitacao_id, licitacao_objeto,
                        monitoramento_id, monitoramento_nome, lido)
                       VALUES ($1,'nova_licitacao',$2,$3,$4,$5,$6,$7,false)""",
                    user_id, title, body,
                    str(tender_id) if tender_id else None,
                    objeto or None,
                    monitor_id,
                    monitor_name or None,
                )
                # Incrementa contador atomicamente na mesma transação
                if monitor_id:
                    await conn.execute(
                        "UPDATE monitoramentos SET total_alertas = COALESCE(total_alertas,0)+1 WHERE id=$1",
                        monitor_id,
                    )
        persisted = True
    except Exception as exc:
        logger.warning("send_monitor_match: alerta DB error: %s", exc)

    metadata = {
        "monitor_id":  monitor_id,
        "tender_id":   str(tender_id),
        "source":      tender.get("source", "pncp"),
    }

    if background_tasks:
        background_tasks.add_task(
            send, user, title, body,
            channels=None, tipo="match", metadata=metadata,
            cta_url="https://licitaim.com.br/licitacoes",
            cta_label="Ver licitação",
        )
    else:
        await send(
            user, title, body,
            channels=None, tipo="match", metadata=metadata,
            cta_url="https://licitaim.com.br/licitacoes",
            cta_label="Ver licitação",
        )

    return persisted


async def send_tender_update(
    user: dict,
    tender: dict,
    changes: dict,
    background_tasks=None,
) -> None:
    """
    Notifica usuário sobre alterações em uma licitação favoritada/monitorada.
    `changes` = {campo: (valor_anterior, valor_novo)}
    """
    from ..db.session import get_pool

    objeto  = tender.get("objeto", "")[:150]
    user_id = str(user.get("id", ""))

    changes_str = "\n".join(
        f"  • {campo}: {ant} → {novo}"
        for campo, (ant, novo) in changes.items()
    )
    title = f"⚠️ Licitação atualizada: {objeto[:60]}"
    body  = f"A licitação a seguir teve alterações:\n\n{objeto}\n\nMudanças:\n{changes_str}"

    # Persiste alerta
    try:
        pool = await get_pool()
        await pool.execute(
            """INSERT INTO alertas
               (user_id, tipo, titulo, descricao, licitacao_id, licitacao_objeto, lido)
               VALUES ($1,'situacao_alterada',$2,$3,$4,$5,false)""",
            user_id, title, body,
            str(tender.get("id", "")),
            objeto or None,
        )
    except Exception as exc:
        logger.warning("send_tender_update: DB error: %s", exc)

    metadata = {
        "tender_id": str(tender.get("id", "")),
        "changes":   {k: {"from": v[0], "to": v[1]} for k, v in changes.items()},
    }

    if background_tasks:
        background_tasks.add_task(
            send, user, title, body,
            channels=None, tipo="update", metadata=metadata,
            cta_url="https://licitaim.com.br/licitacoes",
            cta_label="Ver licitação",
        )
    else:
        await send(
            user, title, body,
            channels=None, tipo="update", metadata=metadata,
            cta_url="https://licitaim.com.br/licitacoes",
            cta_label="Ver licitação",
        )


async def send_document_expiration(
    user: dict,
    certidao: dict,
    dias_restantes: int,
    background_tasks=None,
    ref_key: str | None = None,
) -> bool:
    """Alerta de vencimento de certidão.

    ref_key — chave de deduplicação opcional (armazenada em alertas.licitacao_id).
    Quando fornecida, permite que chamadores detectem registros já existentes antes
    de invocar esta função para evitar envios duplicados em reruns.

    Returns True se o alerta foi persistido com sucesso em `alertas`, False caso contrário.
    A notificação via canais (email, push, etc.) é sempre tentada, independente da persistência.
    """
    from ..db.session import get_pool

    nome    = certidao.get("nome", "Certidão")
    user_id = str(user.get("id", ""))

    if dias_restantes < 0:
        title = f"🚨 Certidão VENCIDA: {nome}"
        body  = f"A certidão '{nome}' venceu há {abs(dias_restantes)} dia(s). Renove imediatamente."
        tipo  = "error"
    elif dias_restantes == 0:
        title = f"🚨 Certidão vence HOJE: {nome}"
        body  = f"A certidão '{nome}' vence hoje. Providencie a renovação urgentemente."
        tipo  = "error"
    else:
        title = f"⚠️ Certidão vence em {dias_restantes}d: {nome}"
        body  = f"A certidão '{nome}' vencerá em {dias_restantes} dia(s). Programe a renovação."
        tipo  = "warning"

    # Persiste alerta (licitacao_id guarda ref_key para deduplicação futura)
    persisted = False
    try:
        pool = await get_pool()
        await pool.execute(
            """INSERT INTO alertas (user_id, tipo, titulo, descricao, licitacao_id, lido)
               VALUES ($1,'prazo_vencendo',$2,$3,$4,false)""",
            user_id, title, body, ref_key,
        )
        persisted = True
    except Exception as exc:
        logger.warning("send_document_expiration: DB error: %s", exc)

    if background_tasks:
        background_tasks.add_task(
            send, user, title, body,
            channels=None, tipo=tipo, metadata={"certidao_id": certidao.get("id")},
            cta_url="https://licitaim.com.br/certidoes",
            cta_label="Gerenciar certidões",
        )
    else:
        await send(user, title, body, channels=None, tipo=tipo,
                   metadata={"certidao_id": certidao.get("id")})

    return persisted


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_channels(user: dict, requested: list[str]) -> list[str]:
    """Filtra canais solicitados pelas preferências do usuário."""
    pref_map = {
        CHANNEL_PUSH:     user.get("notif_push", True),
        CHANNEL_EMAIL:    user.get("notif_email", True),
        CHANNEL_WHATSAPP: user.get("notif_whatsapp", False),
        CHANNEL_TELEGRAM: user.get("notif_telegram", False),
    }
    return [ch for ch in requested if pref_map.get(ch, False)]
