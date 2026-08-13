from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from jose import JWTError, jwt
from .config import get_settings


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(
    subject: str,
    session_version: int = 0,
    expires_delta: Optional[timedelta] = None,
) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=settings.jwt_expire_days))
    payload = {"sub": subject, "exp": expire, "iat": now, "sv": session_version}
    return jwt.encode(payload, settings.get_jwt_secret(), algorithm=settings.jwt_algorithm)


def decode_token_full(token: str) -> Optional[dict]:
    """Return the full decoded payload dict, or None on any error."""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.get_jwt_secret(), algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def decode_token(token: str) -> Optional[str]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.get_jwt_secret(), algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None
