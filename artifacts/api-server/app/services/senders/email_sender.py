"""
EmailSender — envia e-mails transacionais via SMTP (aiosmtplib).
"""
from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger("licitaim.sender.email")


# ── Template HTML ─────────────────────────────────────────────────────────────

def _html_template(title: str, body: str, cta_url: str = "", cta_label: str = "") -> str:
    cta_block = ""
    if cta_url and cta_label:
        cta_block = f"""
        <tr><td style="padding:24px 40px 0">
          <a href="{cta_url}" style="display:inline-block;background:#4f46e5;color:#fff;
             text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:600;
             font-size:14px">{cta_label}</a>
        </td></tr>"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0">
  <tr><td align="center" style="padding:40px 16px">
    <table width="600" cellpadding="0" cellspacing="0"
           style="background:#fff;border-radius:12px;overflow:hidden;
                  box-shadow:0 2px 8px rgba(0,0,0,.08)">
      <!-- Header -->
      <tr><td style="background:#4f46e5;padding:28px 40px">
        <span style="color:#fff;font-size:22px;font-weight:700;letter-spacing:-.5px">
          ⚡ LicitAIM
        </span>
      </td></tr>
      <!-- Body -->
      <tr><td style="padding:32px 40px 8px">
        <h1 style="margin:0 0 16px;font-size:20px;color:#111827;line-height:1.3">{title}</h1>
        <div style="color:#374151;font-size:15px;line-height:1.7">{body.replace(chr(10),'<br>')}</div>
      </td></tr>
      {cta_block}
      <!-- Footer -->
      <tr><td style="padding:32px 40px;color:#9ca3af;font-size:12px;border-top:1px solid #f3f4f6;margin-top:24px">
        Você recebeu este e-mail porque está cadastrado no LicitAIM.<br>
        <a href="https://licitaim.com.br/configuracoes" style="color:#4f46e5">
          Gerenciar preferências de notificação
        </a>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""


# ── Sender ────────────────────────────────────────────────────────────────────

async def send_email(
    to: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    cta_url: str = "",
    cta_label: str = "",
) -> bool:
    """
    Envia e-mail usando aiosmtplib.
    Retorna True em caso de sucesso, False caso contrário (nunca levanta exceção).
    """
    from ...core.config import get_settings
    settings = get_settings()

    if not settings.smtp_user or not settings.smtp_password:
        logger.info(
            "EmailSender: SMTP não configurado — simulando envio para %s | %s", to, subject
        )
        return True   # dev mode: considera enviado

    try:
        import aiosmtplib  # type: ignore

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{settings.smtp_from_name} <{settings.smtp_from}>"
        msg["To"]      = to

        html = body_html or _html_template(subject, body_text, cta_url, cta_label)
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(html,      "html",  "utf-8"))

        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=True,
        )
        logger.info("EmailSender: enviado para %s", to)
        return True

    except Exception as exc:
        logger.warning("EmailSender falhou para %s: %s", to, exc)
        return False
