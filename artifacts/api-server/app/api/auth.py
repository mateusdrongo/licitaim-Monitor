from fastapi import APIRouter, HTTPException, Response, Cookie, Depends
from pydantic import BaseModel, EmailStr, model_validator
from typing import Optional
import uuid
import secrets
import logging
from datetime import datetime, timedelta, timezone
from ..db.session import get_pool
from ..core.security import create_access_token, verify_password, get_password_hash
from ..core.deps import get_current_user

logger = logging.getLogger(__name__)

# Expiry window for reset tokens
RESET_TOKEN_TTL = timedelta(hours=1)

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "licitaim_token"
COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days


class LoginRequest(BaseModel):
    email: str
    password: Optional[str] = None


class RegisterRequest(BaseModel):
    nome: str
    email: str
    password: str
    empresa: Optional[str] = None
    cnpj: Optional[str] = None


class ProfileUpdate(BaseModel):
    notif_email: Optional[bool] = None
    notif_telegram: Optional[bool] = None
    telegram_chat_id: Optional[str] = None

    @model_validator(mode="after")
    def telegram_requires_chat_id(self) -> "ProfileUpdate":
        if self.notif_telegram is True:
            chat_id = (self.telegram_chat_id or "").strip()
            if not chat_id:
                raise ValueError(
                    "O Chat ID do Telegram é obrigatório para ativar as notificações pelo Telegram."
                )
        return self


def _user_response(u: dict) -> dict:
    return {
        "id": u["id"],
        "nome": u["nome"],
        "email": u["email"],
        "empresa": u.get("empresa"),
        "cnpj": u.get("cnpj"),
        "plano": u["plano"],
        "avatarUrl": u.get("avatar_url"),
        "criadoEm": u["criado_em"].isoformat() if u.get("criado_em") else None,
        "notifEmail": u.get("notif_email", True),
        "notifTelegram": u.get("notif_telegram", False),
        "telegramChatId": u.get("telegram_chat_id"),
    }


def _set_auth_cookie(response: Response, user_id: str, session_version: int = 0):
    token = create_access_token(user_id, session_version=session_version)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=COOKIE_MAX_AGE,
    )
    return token


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return _user_response(current_user)


@router.patch("/me")
async def update_me(body: ProfileUpdate, current_user: dict = Depends(get_current_user)):
    """Update notification preferences and Telegram chat ID for the current user."""
    pool = await get_pool()

    updates: list[str] = []
    values: list = []
    idx = 1

    if body.notif_email is not None:
        updates.append(f"notif_email = ${idx}")
        values.append(body.notif_email)
        idx += 1

    if body.notif_telegram is not None:
        updates.append(f"notif_telegram = ${idx}")
        values.append(body.notif_telegram)
        idx += 1

    if body.telegram_chat_id is not None:
        # Allow empty string to clear the chat ID
        chat_id = body.telegram_chat_id.strip() or None
        updates.append(f"telegram_chat_id = ${idx}")
        values.append(chat_id)
        idx += 1

    if not updates:
        return _user_response(current_user)

    updates.append(f"atualizado_em = NOW()")
    values.append(current_user["id"])

    sql = (
        f"UPDATE users SET {', '.join(updates)} WHERE id = ${idx} "
        f"RETURNING id, nome, email, empresa, cnpj, plano, avatar_url, criado_em, "
        f"notif_email, notif_telegram, telegram_chat_id"
    )

    updated = await pool.fetchrow(sql, *values)
    if not updated:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    return _user_response(dict(updated))


@router.post("/login")
async def login(body: LoginRequest, response: Response):
    pool = await get_pool()

    user = await pool.fetchrow(
        "SELECT id, nome, email, empresa, cnpj, plano, avatar_url, senha_hash, criado_em, "
        "notif_email, notif_telegram, telegram_chat_id, session_version "
        "FROM users WHERE email = $1",
        body.email.lower().strip(),
    )

    if not user:
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")

    senha_hash = user["senha_hash"]
    if senha_hash:
        # Account has a password — verify it
        if not body.password or not verify_password(body.password, senha_hash):
            raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")
    # Legacy accounts (senha_hash IS NULL) — allow login without password verification

    _set_auth_cookie(response, user["id"], session_version=user["session_version"])
    return _user_response(dict(user))


@router.post("/register")
async def register(body: RegisterRequest, response: Response):
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="A senha deve ter pelo menos 8 caracteres")

    pool = await get_pool()

    existing = await pool.fetchrow(
        "SELECT id FROM users WHERE email = $1", body.email.lower().strip()
    )
    if existing:
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")

    new_id = str(uuid.uuid4())
    hashed = get_password_hash(body.password)

    user = await pool.fetchrow(
        """INSERT INTO users (id, nome, email, senha_hash, empresa, cnpj, plano)
           VALUES ($1, $2, $3, $4, $5, $6, 'gratuito')
           RETURNING id, nome, email, empresa, cnpj, plano, avatar_url, criado_em,
                     notif_email, notif_telegram, telegram_chat_id""",
        new_id, body.nome, body.email.lower().strip(), hashed, body.empresa, body.cnpj,
    )

    _set_auth_cookie(response, new_id)
    return _user_response(dict(user))


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, samesite="none", secure=True)
    return {"message": "Sessão encerrada com sucesso"}


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest):
    """
    Generates a one-time password-reset token.
    In dev mode (ENVIRONMENT=development, the canonical setting) the link is written
    to the server console at DEBUG level only — never returned to the caller or logged
    at INFO/WARNING level where it could be captured by production log aggregators.
    In production, the link would be dispatched via the configured SMTP service.
    """
    from ..core.config import get_settings as _get_settings
    _is_dev = _get_settings().environment.lower() == "development"

    pool = await get_pool()

    email = body.email.lower().strip()
    user = await pool.fetchrow("SELECT id, nome, email FROM users WHERE email = $1", email)

    # Always return the same generic response to avoid leaking whether the e-mail exists
    _GENERIC_RESPONSE = {"message": "Se o e-mail estiver cadastrado, você receberá um link para redefinir sua senha."}

    if not user:
        return _GENERIC_RESPONSE

    # Invalidate any existing unused tokens for this user
    await pool.execute(
        "UPDATE password_reset_tokens SET used = TRUE WHERE user_id = $1 AND used = FALSE",
        user["id"],
    )

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + RESET_TOKEN_TTL

    await pool.execute(
        """
        INSERT INTO password_reset_tokens (token, user_id, expires_at)
        VALUES ($1, $2, $3)
        """,
        token, user["id"], expires_at,
    )

    if _is_dev:
        # Dev mode: write the reset link to a local file the operator can inspect.
        # The token is NOT emitted to HTTP responses, INFO/WARNING/ERROR logs, or stdout.
        import pathlib as _pathlib
        _dev_log = _pathlib.Path("/tmp/licitaim-dev-resets.log")
        try:
            with _dev_log.open("a") as _f:
                _f.write(f"[DEV] Reset link for {email}: /redefinir-senha?token={token}\n")
            logger.info("[DEV] Password reset token written to %s (check file for link)", _dev_log)
        except Exception as _exc:
            logger.warning("[DEV] Could not write reset token to %s: %s", _dev_log, _exc)
    else:
        # Production: dispatch via SMTP (see follow-up task for full email delivery)
        logger.info("Password reset requested for user_id=%s (email delivery not yet configured)", user["id"])

    return _GENERIC_RESPONSE


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest):
    """
    Validates the reset token and sets the new password atomically.

    The token claim (`used = TRUE`) and the password update happen inside a single
    transaction. The claim itself is conditional (`used = FALSE AND expires_at > NOW()`),
    so concurrent requests with the same token will have only one winner — the second
    will find zero rows claimed and raise an error.
    """
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="A senha deve ter pelo menos 8 caracteres")

    pool = await get_pool()
    new_hash = get_password_hash(body.password)

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Atomically claim the token: only succeeds for an unused, unexpired token.
            claimed = await conn.fetchrow(
                """
                UPDATE password_reset_tokens
                SET    used = TRUE
                WHERE  token      = $1
                  AND  used       = FALSE
                  AND  expires_at > NOW()
                RETURNING user_id
                """,
                body.token,
            )

            if not claimed:
                raise HTTPException(
                    status_code=400,
                    detail="Link de redefinição inválido, expirado ou já utilizado. Solicite um novo.",
                )

            # Increment session_version: all existing JWTs carry the old version
            # and will be rejected by get_current_user and the WS endpoint.
            await conn.execute(
                """
                UPDATE users
                SET senha_hash      = $1,
                    atualizado_em   = NOW(),
                    session_version = session_version + 1
                WHERE id = $2
                """,
                new_hash, claimed["user_id"],
            )

    # Disconnect any active WebSocket sessions for this user (they hold stale tokens)
    from ..services.websocket_manager import get_ws_manager as _get_ws
    await _get_ws().disconnect_all_for_user(claimed["user_id"])

    return {"message": "Senha redefinida com sucesso. Você já pode fazer login."}
