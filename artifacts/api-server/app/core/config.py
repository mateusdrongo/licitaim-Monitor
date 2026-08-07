from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    database_url: str = ""
    jwt_secret: str = "licitaim-dev-secret-change-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 30
    environment: str = "development"

    # PNCP
    pncp_base_url: str = "https://pncp.gov.br/api/consulta/v1"

    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = ""      # cai para redis_url
    celery_result_backend: str = ""  # cai para redis_url

    # Email (SMTP)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@licitaim.com.br"
    smtp_from_name: str = "LicitAIM"

    # Telegram Bot
    telegram_bot_token: str = ""

    # WhatsApp (Meta / Twilio — MVP: apenas loga)
    whatsapp_api_url: str = ""
    whatsapp_token: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}

    def get_database_url(self) -> str:
        return os.environ.get("DATABASE_URL", self.database_url)

    def get_jwt_secret(self) -> str:
        return os.environ.get("SESSION_SECRET",
               os.environ.get("JWT_SECRET", self.jwt_secret))

    def get_redis_url(self) -> str:
        return os.environ.get("REDIS_URL", self.redis_url)

    def get_celery_broker(self) -> str:
        return (os.environ.get("CELERY_BROKER_URL")
                or self.celery_broker_url
                or self.get_redis_url())

    def get_celery_backend(self) -> str:
        return (os.environ.get("CELERY_RESULT_BACKEND")
                or self.celery_result_backend
                or self.get_redis_url())


@lru_cache
def get_settings() -> Settings:
    return Settings()
