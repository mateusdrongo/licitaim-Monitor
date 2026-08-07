"""
Configurações do collector — compatível com as env vars do backend FastAPI.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class CollectorSettings(BaseSettings):
    # Banco de dados (mesma var do backend)
    database_url: str = os.environ.get("DATABASE_URL", "")

    # Elasticsearch
    elasticsearch_url: str = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")

    # RabbitMQ / Celery broker
    rabbitmq_url: str = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672//")
    celery_broker_url: str = os.environ.get("CELERY_BROKER_URL", "")      # cai para rabbitmq_url
    celery_result_backend: str = os.environ.get("CELERY_RESULT_BACKEND",
                                                  os.environ.get("REDIS_URL", "redis://localhost:6379/0"))

    # PNCP
    pncp_base_url: str = "https://pncp.gov.br/api/consulta/v1"
    pncp_page_size: int = 50
    pncp_rate_limit_sleep: float = 0.5    # segundos entre requests
    pncp_max_pages: int = 200             # segurança contra loops infinitos

    # Playwright / scraping
    headless: bool = True
    playwright_timeout_ms: int = 30_000

    # Retry (tenacity)
    retry_attempts: int = 5
    retry_min_wait: float = 1.0
    retry_max_wait: float = 60.0

    # Logging
    log_level: str = os.environ.get("LOG_LEVEL", "INFO")

    model_config = {"env_file": ".env", "extra": "ignore"}

    def get_broker_url(self) -> str:
        return self.celery_broker_url or self.rabbitmq_url


@lru_cache
def get_settings() -> CollectorSettings:
    return CollectorSettings()
