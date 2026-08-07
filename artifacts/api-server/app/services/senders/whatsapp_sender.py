"""
WhatsAppSender — integração Meta Business API / Twilio.
MVP: apenas loga a mensagem. Quando as credenciais estiverem configuradas,
usa httpx para chamar a API.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger("licitaim.sender.whatsapp")


async def send_whatsapp(
    phone: str,
    message: str,
    template_name: Optional[str] = None,
    template_params: Optional[list[str]] = None,
) -> bool:
    """
    Envia mensagem WhatsApp via Meta Cloud API.
    Se WHATSAPP_TOKEN não configurado, apenas loga (MVP).
    """
    from ...core.config import get_settings
    settings = get_settings()

    # Normaliza número (apenas dígitos, sem +)
    phone_clean = "".join(c for c in phone if c.isdigit())

    if not settings.whatsapp_token or not settings.whatsapp_api_url:
        logger.info(
            "WhatsAppSender [MVP-log] → %s: %s", phone_clean, message[:120]
        )
        return True   # MVP: simula sucesso

    try:
        if template_name:
            # Mensagem baseada em template (para notificações fora da janela de 24h)
            payload: dict = {
                "messaging_product": "whatsapp",
                "to": phone_clean,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": "pt_BR"},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": p}
                                for p in (template_params or [])
                            ],
                        }
                    ],
                },
            }
        else:
            # Mensagem de texto livre (dentro da janela de 24h)
            payload = {
                "messaging_product": "whatsapp",
                "to": phone_clean,
                "type": "text",
                "text": {"body": message},
            }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                settings.whatsapp_api_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.whatsapp_token}",
                    "Content-Type":  "application/json",
                },
            )
            if resp.is_success:
                logger.info("WhatsAppSender: enviado para %s", phone_clean)
                return True
            logger.warning(
                "WhatsAppSender: status %d para %s — %s",
                resp.status_code, phone_clean, resp.text[:200],
            )
            return False

    except Exception as exc:
        logger.warning("WhatsAppSender falhou para %s: %s", phone_clean, exc)
        return False
