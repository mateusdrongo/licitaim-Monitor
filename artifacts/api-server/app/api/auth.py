from fastapi import APIRouter, HTTPException, Response, Cookie, Depends
from pydantic import BaseModel, EmailStr, model_validator
from typing import Optional
import uuid
from ..db.session import get_pool
from ..core.security import create_access_token, verify_password, get_password_hash
from ..core.deps import get_current_user

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


def _set_auth_cookie(response: Response, user_id: str):
    token = create_access_token(user_id)
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
        "SELECT id, nome, email, empresa, cnpj, plano, avatar_url, senha_hash, criado_em "
        "FROM users WHERE email = $1",
        body.email.lower().strip(),
    )

    if not user:
        # Demo mode: auto-create user on first login
        new_id = str(uuid.uuid4())
        nome = body.email.split("@")[0].capitalize()
        user = await pool.fetchrow(
            """INSERT INTO users (id, nome, email, plano, empresa)
               VALUES ($1, $2, $3, 'profissional', 'Minha Empresa Ltda')
               RETURNING id, nome, email, empresa, cnpj, plano, avatar_url, senha_hash, criado_em""",
            new_id, nome, body.email.lower().strip(),
        )

    _set_auth_cookie(response, user["id"])
    return _user_response(dict(user))


@router.post("/register")
async def register(body: RegisterRequest, response: Response):
    pool = await get_pool()

    existing = await pool.fetchrow("SELECT id FROM users WHERE email = $1", body.email.lower().strip())
    if existing:
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")

    new_id = str(uuid.uuid4())
    hashed = get_password_hash(body.password) if body.password else None

    user = await pool.fetchrow(
        """INSERT INTO users (id, nome, email, senha_hash, empresa, cnpj, plano)
           VALUES ($1, $2, $3, $4, $5, $6, 'gratuito')
           RETURNING id, nome, email, empresa, cnpj, plano, avatar_url, criado_em""",
        new_id, body.nome, body.email.lower().strip(), hashed, body.empresa, body.cnpj,
    )

    _set_auth_cookie(response, new_id)
    return _user_response(dict(user))


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, samesite="none", secure=True)
    return {"message": "Sessão encerrada com sucesso"}
