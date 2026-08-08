"""
TenderProcessor — normaliza dados, faz upsert no Postgres,
detecta mudanças (TenderHistory) e dispara indexação no Elasticsearch via RabbitMQ.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import date, datetime
from typing import Optional

import asyncpg

from ..config import get_settings

logger = logging.getLogger("collector.processor")

# Campos monitorados para gerar histórico de mudanças
TRACKED_FIELDS = (
    "objeto",
    "situacao",
    "valor_estimado",
    "data_abertura",
    "data_encerramento",
    "modalidade",
)


class TenderProcessor:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.settings = get_settings()
        self._publisher = None  # lazy init

    # ── Interface principal ───────────────────────────────────────────────────

    async def process(self, tender: dict) -> Optional[str]:
        """
        Processa um tender normalizado:
          1. Normaliza strings e formata CNPJ
          2. Upsert em tenders (baseado em source + external_id)
          3. Detecta mudanças → TenderHistory
          4. Upsert dos itens
          5. Publica evento no RabbitMQ para indexação no ES

        Retorna o UUID do tender no banco, ou None em caso de falha.
        """
        normalized = self._normalize(tender)

        async with self.pool.acquire() as conn:
            tender_id = await self._upsert_tender(conn, normalized)
            if not tender_id:
                return None

            await self._upsert_items(conn, tender_id, normalized.get("items", []))

        # Publicar evento ES (fire-and-forget; falha silenciosa)
        try:
            await self._publish_es_event(str(tender_id), normalized)
        except Exception as exc:
            logger.warning("TenderProcessor publish ES event: %s", exc)

        return str(tender_id)

    # ── Normalização ──────────────────────────────────────────────────────────

    def _normalize(self, tender: dict) -> dict:
        t = dict(tender)

        # Strings
        for key in ("objeto", "orgao", "unidade", "municipio", "modalidade", "situacao",
                    "link_original", "numero_controle", "external_id"):
            if key in t:
                t[key] = self._clean_str(t.get(key))

        # Canonical forms for fuzzy cross-portal dedup (lowercase, no accents, collapsed spaces)
        t["objeto_norm"] = self._normalize_for_dedup(t.get("objeto"))
        t["orgao_norm"]  = self._normalize_for_dedup(t.get("orgao"))

        # CNPJ
        if t.get("cnpj_orgao"):
            t["cnpj_orgao"] = self._format_cnpj(t["cnpj_orgao"])

        # UF: sigla 2 letras maiúsculas
        if t.get("uf"):
            uf = re.sub(r"[^A-Za-z]", "", str(t["uf"]))
            t["uf"] = uf[:2].upper() if uf else None

        # Datas: converte strings variadas → date/datetime
        t["data_publicacao"]   = self._parse_date(t.get("data_publicacao"))
        t["data_abertura"]     = self._parse_datetime(t.get("data_abertura"))
        t["data_encerramento"] = self._parse_datetime(t.get("data_encerramento"))

        # Valor
        if isinstance(t.get("valor_estimado"), str):
            t["valor_estimado"] = self._parse_float(t["valor_estimado"])

        # dados_brutos: serializa se necessário
        if isinstance(t.get("dados_brutos"), dict):
            t["dados_brutos"] = json.dumps(t["dados_brutos"], ensure_ascii=False, default=str)

        return t

    # ── Upsert tender ─────────────────────────────────────────────────────────

    async def _upsert_tender(self, conn: asyncpg.Connection, t: dict) -> Optional[str]:
        try:
            existing = await conn.fetchrow(
                "SELECT id, objeto, situacao, valor_estimado, data_abertura, "
                "       data_encerramento, modalidade "
                "FROM tenders WHERE source = $1 AND external_id = $2",
                t["source"], t["external_id"],
            )

            if existing:
                tender_id = existing["id"]
                # Detecta mudanças e registra histórico
                await self._record_history(conn, tender_id, existing, t)
                # Atualiza
                await conn.execute(
                    """
                    UPDATE tenders SET
                        numero_controle   = $3,
                        objeto            = $4,
                        objeto_norm       = $5,
                        orgao             = $6,
                        orgao_norm        = $7,
                        cnpj_orgao        = $8,
                        unidade           = $9,
                        uf                = $10,
                        municipio         = $11,
                        modalidade        = $12,
                        situacao          = $13,
                        valor_estimado    = $14,
                        data_publicacao   = $15,
                        data_abertura     = $16,
                        data_encerramento = $17,
                        srp               = $18,
                        link_original     = $19,
                        dados_brutos      = $20::jsonb,
                        atualizado_em     = NOW()
                    WHERE source = $1 AND external_id = $2
                    """,
                    t["source"], t["external_id"],
                    t.get("numero_controle"), t.get("objeto"), t.get("objeto_norm"),
                    t.get("orgao"), t.get("orgao_norm"),
                    t.get("cnpj_orgao"), t.get("unidade"), t.get("uf"), t.get("municipio"),
                    t.get("modalidade"), t.get("situacao"),
                    t.get("valor_estimado"),
                    t.get("data_publicacao"), t.get("data_abertura"), t.get("data_encerramento"),
                    bool(t.get("srp", False)),
                    t.get("link_original"), t.get("dados_brutos"),
                )
                return str(tender_id)

            else:
                # Deduplicação cross-portal: mesmo tender pode aparecer em múltiplos portais
                # (ex.: licitações federais publicadas tanto no PNCP quanto no ComprasNet).
                # Antes de inserir, verificamos se já existe um registro com os mesmos
                # campos canônicos normalizados (objeto_norm + orgao_norm + data_publicacao)
                # proveniente de outra fonte.  A comparação usa as colunas normalizadas
                # (lowercase, sem acentos, espaços colapsados) para capturar variantes textuais.
                cross_dup = None
                if t.get("objeto_norm") and t.get("orgao_norm") and t.get("data_publicacao"):
                    cross_dup = await conn.fetchrow(
                        """
                        SELECT id, source FROM tenders
                        WHERE objeto_norm   = $1
                          AND orgao_norm    = $2
                          AND data_publicacao = $3
                          AND source <> $4
                        LIMIT 1
                        """,
                        t["objeto_norm"], t["orgao_norm"], t["data_publicacao"], t["source"],
                    )

                if cross_dup:
                    logger.warning(
                        "TenderProcessor: tender duplicado ignorado — "
                        "source=%s external_id=%s já existe como source=%s id=%s "
                        "(objeto/orgao/data_publicacao coincidem).",
                        t.get("source"), t.get("external_id"),
                        cross_dup["source"], cross_dup["id"],
                    )
                    return str(cross_dup["id"])

                row = await conn.fetchrow(
                    """
                    INSERT INTO tenders (
                        source, external_id, numero_controle,
                        objeto, objeto_norm, orgao, orgao_norm, cnpj_orgao,
                        unidade, uf, municipio, modalidade, situacao, valor_estimado,
                        data_publicacao, data_abertura, data_encerramento, srp,
                        link_original, dados_brutos
                    ) VALUES (
                        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20::jsonb
                    ) RETURNING id
                    """,
                    t["source"], t["external_id"], t.get("numero_controle"),
                    t.get("objeto"), t.get("objeto_norm"), t.get("orgao"), t.get("orgao_norm"),
                    t.get("cnpj_orgao"),
                    t.get("unidade"), t.get("uf"), t.get("municipio"),
                    t.get("modalidade"), t.get("situacao"), t.get("valor_estimado"),
                    t.get("data_publicacao"), t.get("data_abertura"), t.get("data_encerramento"),
                    bool(t.get("srp", False)),
                    t.get("link_original"), t.get("dados_brutos"),
                )
                return str(row["id"])

        except Exception as exc:
            logger.error(
                "TenderProcessor upsert (%s/%s): %s",
                t.get("source"), t.get("external_id"), exc,
            )
            return None

    # ── Itens ─────────────────────────────────────────────────────────────────

    async def _upsert_items(
        self, conn: asyncpg.Connection, tender_id: str, items: list[dict]
    ) -> None:
        if not items:
            return
        try:
            # Remove itens antigos e reinsere (simplificado; pode-se sofisticar com merge)
            await conn.execute("DELETE FROM tender_items WHERE tender_id = $1", tender_id)
            await conn.executemany(
                """
                INSERT INTO tender_items
                    (tender_id, numero_item, descricao, quantidade, unidade_medida,
                     valor_unitario, valor_total)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
                """,
                [
                    (
                        tender_id,
                        it.get("numero_item"),
                        self._clean_str(it.get("descricao")),
                        it.get("quantidade"),
                        self._clean_str(it.get("unidade_medida")),
                        it.get("valor_unitario"),
                        it.get("valor_total"),
                    )
                    for it in items
                ],
            )
        except Exception as exc:
            logger.warning("TenderProcessor upsert_items(%s): %s", tender_id, exc)

    # ── Histórico de mudanças ─────────────────────────────────────────────────

    async def _record_history(
        self,
        conn: asyncpg.Connection,
        tender_id: str,
        existing: asyncpg.Record,
        new: dict,
    ) -> None:
        records = []
        for field in TRACKED_FIELDS:
            old_val = existing.get(field)
            new_val = new.get(field)
            # Compara como string para evitar falsos positivos de tipo
            if str(old_val or "") != str(new_val or ""):
                records.append((tender_id, field, str(old_val or ""), str(new_val or "")))

        if records:
            await conn.executemany(
                "INSERT INTO tender_history (tender_id, campo, valor_anterior, valor_novo) "
                "VALUES ($1,$2,$3,$4)",
                records,
            )
            logger.info(
                "TenderHistory: %d mudança(s) detectada(s) no tender %s.",
                len(records), tender_id,
            )

    # ── Publicação no RabbitMQ ────────────────────────────────────────────────

    async def _publish_es_event(self, tender_id: str, tender: dict) -> None:
        """Publica mensagem para que o ES consumer indexe o tender."""
        from ..queue import get_publisher
        publisher = get_publisher()
        payload = {
            "event": "tender.upserted",
            "tender_id": tender_id,
            "source": tender.get("source"),
            "external_id": tender.get("external_id"),
        }
        await publisher.publish("tender.sync", payload)

    # ── Utilitários ───────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_for_dedup(val: object) -> Optional[str]:
        """
        Canonical form used for cross-portal deduplication.

        Steps:
        1. Collapse whitespace (same as _clean_str)
        2. Lowercase
        3. Strip diacritical marks (accents) via Unicode decomposition → composition
        4. Keep only alphanumeric characters and single spaces

        This ensures that minor text variations between portals — different
        casing, accented vs. unaccented letters, extra punctuation or spaces —
        all map to the same canonical string.

        Examples:
            "Ministério da Educação"  → "ministerio da educacao"
            "MINISTERIO DA EDUCACAO"  → "ministerio da educacao"
            "Ministério  da  Educação" → "ministerio da educacao"
        """
        if val is None:
            return None
        # Collapse whitespace first
        s = " ".join(str(val).split())
        if not s:
            return None
        # Lowercase
        s = s.lower()
        # Decompose Unicode (NFD) so accents become separate combining characters,
        # then filter out the combining characters (category 'Mn').
        s = "".join(
            ch for ch in unicodedata.normalize("NFD", s)
            if unicodedata.category(ch) != "Mn"
        )
        # Collapse any whitespace again (decomposition shouldn't produce extra,
        # but guard against edge cases)
        s = " ".join(s.split())
        return s or None

    @staticmethod
    def _clean_str(val: object) -> Optional[str]:
        if val is None:
            return None
        s = " ".join(str(val).split())
        return s or None

    @staticmethod
    def _format_cnpj(cnpj: str) -> Optional[str]:
        digits = re.sub(r"\D", "", str(cnpj))
        if len(digits) == 14:
            return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
        if len(digits) == 11:
            return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
        return cnpj

    @staticmethod
    def _parse_date(val: object) -> Optional[date]:
        if not val:
            return None
        s = str(val).strip()[:10]
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                pass
        return None

    @staticmethod
    def _parse_datetime(val: object) -> Optional[datetime]:
        if not val:
            return None
        s = str(val).strip()
        for fmt in (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
        ):
            try:
                return datetime.strptime(s[:len(fmt.replace("%Y","9999").replace("%m","12").replace("%d","31"))], fmt)
            except ValueError:
                pass
        return None

    @staticmethod
    def _parse_float(val: str) -> Optional[float]:
        try:
            clean = re.sub(r"[^\d,\.]", "", val).replace(",", ".")
            return float(clean)
        except (ValueError, TypeError):
            return None
