"""
TelegramSender — envia mensagens via Telegram Bot API usando httpx.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger("licitaim.sender.telegram")

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


async def send_telegram(
    chat_id: str,
    text: str,
    parse_mode: str = "HTML",
    disable_preview: bool = True,
) -> bool:
    """
    Envia mensagem Telegram para chat_id.
    Se TELEGRAM_BOT_TOKEN não configurado, apenas loga.
    """
    from ...core.config import get_settings
    settings = get_settings()

    if not settings.telegram_bot_token:
        logger.info(
            "TelegramSender [MVP-log] → chat_id=%s: %s", chat_id, text[:120]
        )
        return True   # sem token configurado → simula sucesso

    url = TELEGRAM_API.format(token=settings.telegram_bot_token)
    payload = {
        "chat_id":                  chat_id,
        "text":                     text,
        "parse_mode":               parse_mode,
        "disable_web_page_preview": disable_preview,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            if data.get("ok"):
                logger.info("TelegramSender: enviado para chat_id=%s", chat_id)
                return True
            logger.warning(
                "TelegramSender: erro para chat_id=%s — %s", chat_id, data
            )
            return False

    except Exception as exc:
        logger.warning("TelegramSender falhou para chat_id=%s: %s", chat_id, exc)
        return False


def _fmt_monitor_match(monitor_name: str, tender: dict) -> str:
    """Formata mensagem HTML de match de monitor para Telegram."""
    valor = tender.get("valorEstimado") or tender.get("valor_estimado")
    valor_str = (
        f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if valor else "Não informado"
    )
    return (
        f"🔔 <b>Novo match no monitor</b>: {monitor_name}\n\n"
        f"📋 <b>Objeto:</b> {tender.get('objeto','')[:200]}\n"
        f"🏢 <b>Órgão:</b> {tender.get('orgao','')}\n"
        f"📍 <b>UF:</b> {tender.get('uf','')}\n"
        f"💰 <b>Valor:</b> {valor_str}\n"
        f"📅 <b>Abertura:</b> {tender.get('dataAbertura') or tender.get('data_abertura','')}\n\n"
        f"🔗 <a href='https://licitaim.com.br/licitacoes'>Ver no LicitAIM</a>"
    )


def _fmt_tender_update(tender: dict, changes: dict) -> str:
    """Formata mensagem HTML de atualização de tender para Telegram."""
    lines = [f"⚠️ <b>Licitação atualizada</b>\n"]
    lines.append(f"📋 {tender.get('objeto','')[:150]}\n")
    for field, (old, new) in changes.items():
        lines.append(f"  • <b>{field}:</b> {old} → {new}")
    lines.append(f"\n🔗 <a href='https://licitaim.com.br/licitacoes'>Ver detalhes</a>")
    return "\n".join(lines)
