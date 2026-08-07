"""
BaseScraper — interface abstrata para todos os scrapers de portais de licitação.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import date
from typing import AsyncIterator

from .config import CollectorSettings, get_settings


class BaseScraper(ABC):
    """
    Classe base para scrapers de portais de licitação.

    Cada scraper deve implementar:
      - scrape_by_date(start, end): itera sobre licitações publicadas no período
      - scrape_by_id(external_id):  retorna uma licitação específica pelo ID do portal

    Os dados retornados devem seguir o schema normalizado (ver TenderProcessor).
    """

    SOURCE: str  # identificador do portal, ex: "pncp", "comprasnet"

    def __init__(self, settings: CollectorSettings | None = None):
        self.settings = settings or get_settings()
        self.logger = logging.getLogger(f"collector.{self.SOURCE}")

    # ── Interface pública ─────────────────────────────────────────────────────

    @abstractmethod
    async def scrape_by_date(
        self,
        start: date,
        end: date,
    ) -> AsyncIterator[dict]:
        """
        Itera assincronamente sobre licitações publicadas entre start e end (inclusive).
        Cada item yielded é um dict já mapeado para o schema normalizado.
        """
        ...  # pragma: no cover

    @abstractmethod
    async def scrape_by_id(self, external_id: str) -> dict | None:
        """
        Retorna dados de uma licitação específica pelo ID externo do portal,
        ou None se não encontrado.
        """
        ...  # pragma: no cover

    # ── Hooks opcionais ───────────────────────────────────────────────────────

    async def on_start(self) -> None:
        """Chamado antes de iniciar o scraping (setup de recursos, autenticação, etc.)."""
        pass

    async def on_finish(self) -> None:
        """Chamado ao terminar o scraping (cleanup de recursos, fechar browser, etc.)."""
        pass

    # ── Utilitários comuns ────────────────────────────────────────────────────

    def _normalize_str(self, val: object) -> str:
        """Remove espaços extras e converte para string."""
        if val is None:
            return ""
        return " ".join(str(val).split())

    def _safe_float(self, val: object) -> float | None:
        if val is None:
            return None
        try:
            return float(str(val).replace(",", ".").replace("R$", "").replace(" ", ""))
        except (ValueError, TypeError):
            return None

    def _safe_int(self, val: object) -> int | None:
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None
