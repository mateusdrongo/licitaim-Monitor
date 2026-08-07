from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from .config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.jwt_expire_days)
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.get_jwt_secret(), algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[str]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.get_jwt_secret(), algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None
