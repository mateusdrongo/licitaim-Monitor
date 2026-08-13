"""
licitacoes_repo.py — Operações de banco para o cache de licitações.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Flag que indica se o DDL de bootstrap foi executado com sucesso.
# Se False, search e upsert retornam imediatamente sem bater no banco,
# evitando erros de "relação inexistente".
_cache_ready: bool = False


def set_cache_ready(ok: bool) -> None:
    global _cache_ready
    _cache_ready = ok


# ── Cobertura do cache — modelo global ────────────────────────────────────────
#
# Design:  UMA única linha na tabela de cobertura, com scope_key=GLOBAL_SCOPE_KEY.
CANONICAL_WINDOW_DAYS = 30       # janela padrão — deve coincidir com scheduler
GLOBAL_SCOPE_KEY      = "global_30d"
_COVERAGE_TTL         = timedelta(hours=6)   # 1 intervalo entre crons (4×/dia)


async def record_global_coverage(pool: asyncpg.Pool, total_found: int, is_complete: bool) -> None:
    """Registra (ou atualiza) o resultado do sync global."""
    if not _cache_ready:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO licitacoes_cache_coverage
                    (scope_key, last_sync, total_found, is_complete, window_days)
                VALUES ($1, NOW(), $2, $3, $4)
                ON CONFLICT (scope_key) DO UPDATE
                    SET last_sync   = NOW(),
                        total_found = EXCLUDED.total_found,
                        is_complete = EXCLUDED.is_complete,
                        window_days = EXCLUDED.window_days
                """,
                GLOBAL_SCOPE_KEY, total_found, is_complete, CANONICAL_WINDOW_DAYS,
            )
    except Exception as exc:
        logger.warning("record_global_coverage: %s", exc)


_MODAL_NAME_TO_CODE: dict[str, int] = {
    "pregão eletrônico": 6, "pregão": 6, "pregão presencial": 7,
    "concorrência eletrônica": 4, "concorrência": 4, "concorrencia": 4,
    "concorrência presencial": 5,
    "dispensa de licitação": 8, "dispensa": 8,
    "inexigibilidade": 9,
    "credenciamento": 12,
    "concurso": 3,
    "diálogo competitivo": 2,
    "leilão": 1,
}


def _parse_ts(val: Any) -> datetime | None:
    if not val:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val
    try:
        s = str(val).strip()
        if "T" in s:
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            elif "+" not in s and len(s) == 19:
                s += "+00:00"
        else:
            s += "T00:00:00+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _modal_code(nome: str | None) -> int | None:
    if not nome:
        return None
    lower = nome.lower()
    for k, v in _MODAL_NAME_TO_CODE.items():
        if k in lower:
            return v
    return None


# Campos rastreados para detecção de mudanças em licitações favoritadas.
# Cada tupla é (chave_no_item_dict, coluna_na_licitacoes_cache).
_CHANGE_TRACKED_FIELDS: list[tuple[str, str]] = [
    ("situacao",       "situacao"),
    ("valor_estimado", "valor_estimado"),
    ("modalidade",     "modalidade"),
    ("objeto",         "objeto"),
]


def _tender_field_changed(new_val: Any, old_val: Any) -> bool:
    """Compara novo e antigo valor de um campo rastreado de forma uniforme."""
    try:
        return float(new_val) != float(old_val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(new_val or "").strip() != str(old_val or "").strip()


async def upsert_licitacoes(
    pool: asyncpg.Pool,
    items: list[dict],
    fonte: str = "pncp",
) -> tuple[int, int, list[dict]]:
    """
    Insere ou atualiza licitações no cache.
    Retorna (inseridos, atualizados, changed_tenders).

    `changed_tenders` é uma lista de dicts dos itens cujos campos rastreados
    (situacao, valor_estimado, modalidade, objeto) mudaram em relação ao snapshot
    anterior no banco. O chamador deve usar essa lista para disparar alertas de
    atualização para usuários que favoritaram as licitações correspondentes.
    """
    if not items or not _cache_ready:
        return 0, 0, []

    inseridos = 0
    atualizados = 0
    changed_tenders: list[dict] = []

    sql = """
        INSERT INTO licitacoes_cache (
            numero, id, ano, objeto, orgao_nome, orgao_cnpj, uf, municipio,
            modalidade, modalidade_codigo, modo_disputa, situacao, valor_estimado,
            data_publicacao, data_abertura, data_encerramento,
            esfera, poder, srp, numero_processo, informacao_complementar,
            amparo_legal, raw_json, fonte, atualizado_em
        ) VALUES (
            $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,
            $17,$18,$19,$20,$21,$22,$23,$24,NOW()
        )
        ON CONFLICT (numero) DO UPDATE SET
            id                      = EXCLUDED.id,
            ano                     = EXCLUDED.ano,
            objeto                  = EXCLUDED.objeto,
            orgao_nome              = EXCLUDED.orgao_nome,
            orgao_cnpj              = EXCLUDED.orgao_cnpj,
            uf                      = EXCLUDED.uf,
            municipio               = EXCLUDED.municipio,
            modalidade              = EXCLUDED.modalidade,
            modalidade_codigo       = EXCLUDED.modalidade_codigo,
            modo_disputa            = EXCLUDED.modo_disputa,
            situacao                = EXCLUDED.situacao,
            valor_estimado          = EXCLUDED.valor_estimado,
            data_publicacao         = EXCLUDED.data_publicacao,
            data_abertura           = EXCLUDED.data_abertura,
            data_encerramento       = EXCLUDED.data_encerramento,
            esfera                  = EXCLUDED.esfera,
            poder                   = EXCLUDED.poder,
            srp                     = EXCLUDED.srp,
            numero_processo         = EXCLUDED.numero_processo,
            informacao_complementar = EXCLUDED.informacao_complementar,
            amparo_legal            = EXCLUDED.amparo_legal,
            raw_json                = EXCLUDED.raw_json,
            fonte                   = EXCLUDED.fonte,
            atualizado_em           = NOW()
        RETURNING (xmax = 0) AS inserted
    """

    async with pool.acquire() as conn:
        # ── Pre-fetch snapshots para detecção de mudanças ──────────────────────
        # Buscamos apenas os campos rastreados antes do upsert para compará-los
        # depois. Isso evita depender de RETURNING old.* (requer PostgreSQL ≥ 17).
        numeros = [
            item.get("numero") or item.get("id")
            for item in items
            if item.get("numero") or item.get("id")
        ]
        existing_rows: dict[str, dict] = {}
        if numeros:
            try:
                prefetch = await conn.fetch(
                    """SELECT numero,
                              situacao,
                              valor_estimado::text AS valor_estimado,
                              modalidade,
                              objeto
                         FROM licitacoes_cache
                        WHERE numero = ANY($1::text[])""",
                    numeros,
                )
                existing_rows = {r["numero"]: dict(r) for r in prefetch}
            except Exception as exc:
                # Falha não crítica — continuamos sem detecção de mudanças neste ciclo.
                logger.warning(
                    "upsert_licitacoes: pre-fetch falhou, mudanças não detectadas: %s", exc
                )

        for item in items:
            numero = item.get("numero") or item.get("id")
            if not numero:
                continue
            try:
                row = await conn.fetchrow(
                    sql,
                    numero,
                    item.get("id") or numero,
                    item.get("ano"),
                    item.get("objeto"),
                    item.get("orgao_nome"),
                    item.get("orgao_cnpj"),
                    item.get("uf"),
                    item.get("municipio"),
                    item.get("modalidade"),
                    _modal_code(item.get("modalidade")),
                    item.get("modo_disputa"),
                    item.get("situacao"),
                    float(item["valor_estimado"]) if item.get("valor_estimado") is not None else None,
                    _parse_ts(
                        item.get("data_publicacao_pncp")
                        or item.get("data_publicacao")
                        or item.get("criado_em")
                    ),
                    _parse_ts(item.get("data_abertura")),
                    _parse_ts(item.get("data_encerramento")),
                    item.get("esfera"),
                    item.get("poder"),
                    bool(item.get("srp", False)),
                    item.get("numero_processo"),
                    item.get("informacao_complementar"),
                    item.get("amparo_legal"),
                    json.dumps(item, default=str),
                    fonte,
                )
                was_inserted = bool(row and row["inserted"])
                if was_inserted:
                    inseridos += 1
                else:
                    atualizados += 1
                    # Detecta mudanças em campos rastreados para alertas de atualização
                    old = existing_rows.get(numero)
                    if old:
                        has_change = any(
                            _tender_field_changed(item.get(item_key), old.get(cache_col))
                            for item_key, cache_col in _CHANGE_TRACKED_FIELDS
                            if item.get(item_key) is not None
                        )
                        if has_change:
                            changed_tenders.append({**item, "numero": numero})
            except Exception as exc:
                logger.warning("upsert_licitacoes skip '%s': %s", numero, exc)

    return inseridos, atualizados, changed_tenders


async def get_cache_stats(pool: asyncpg.Pool) -> dict:
    """
    Retorna estatísticas do cache de licitações:
    - total: quantidade de licitações no banco
    - last_sync: timestamp do último sync global (ISO string ou None)
    - fonte_predominante: fonte mais comum no cache ("pncp", "dadosabertos", etc.)
    """
    if not _cache_ready:
        return {"total": 0, "last_sync": None, "fonte_predominante": None}
    try:
        async with pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM licitacoes_cache") or 0
            cov_row = await conn.fetchrow(
                "SELECT last_sync FROM licitacoes_cache_coverage WHERE scope_key = $1",
                GLOBAL_SCOPE_KEY,
            )
            fonte_row = await conn.fetchrow(
                """
                SELECT fonte, COUNT(*) AS cnt
                FROM licitacoes_cache
                GROUP BY fonte
                ORDER BY cnt DESC
                LIMIT 1
                """
            )
            # Fallback: se a linha de cobertura não existir, usa o MAX(atualizado_em)
            # das próprias licitações (garante que nunca mostre "nunca" quando há dados)
            fallback_ts = None
            if not (cov_row and cov_row["last_sync"]) and total > 0:
                fallback_ts = await conn.fetchval(
                    "SELECT MAX(atualizado_em) FROM licitacoes_cache"
                )

        last_sync_iso: str | None = None
        raw_ts = (cov_row["last_sync"] if cov_row and cov_row["last_sync"] else fallback_ts)
        if raw_ts:
            ts = raw_ts
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            last_sync_iso = ts.isoformat()

        fonte = fonte_row["fonte"] if fonte_row else None
        return {
            "total": int(total),
            "last_sync": last_sync_iso,
            "fonte_predominante": fonte,
        }
    except Exception as exc:
        logger.warning("get_cache_stats: %s", exc)
        return {"total": 0, "last_sync": None, "fonte_predominante": None}


async def search_licitacoes_cache(
    pool: asyncpg.Pool,     # noqa: ARG001 — não usado se _cache_ready=False
    *,
    q: str | None = None,
    uf: str | None = None,
    modalidade_codigo: int | None = None,
    situacao: str | None = None,
    somente_vigentes: bool = False,
    valor_min: float | None = None,
    valor_max: float | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[dict], int]:
    """
    Busca licitações no cache do banco com filtros.
    Retorna (itens, total). Retorna ([], 0) se o cache ainda não está disponível.
    """
    if not _cache_ready:
        return [], 0

    conditions: list[str] = []
    args: list[Any] = []
    idx = 1

    if q:
        conditions.append(
            f"(objeto ILIKE ${idx} OR orgao_nome ILIKE ${idx} OR numero ILIKE ${idx})"
        )
        args.append(f"%{q}%")
        idx += 1

    if uf:
        conditions.append(f"uf = ${idx}")
        args.append(uf.upper())
        idx += 1

    if modalidade_codigo is not None:
        conditions.append(f"modalidade_codigo = ${idx}")
        args.append(modalidade_codigo)
        idx += 1

    # somente_vigentes sobrepõe situacao — filtra aberta + em_andamento
    if somente_vigentes:
        conditions.append(f"situacao = ANY(${idx}::text[])")
        args.append(["aberta", "em_andamento"])
        idx += 1
    elif situacao:
        conditions.append(f"situacao = ${idx}")
        args.append(situacao)
        idx += 1

    if valor_min is not None:
        conditions.append(f"valor_estimado >= ${idx}")
        args.append(valor_min)
        idx += 1

    if valor_max is not None:
        conditions.append(f"(valor_estimado IS NULL OR valor_estimado <= ${idx})")
        args.append(valor_max)
        idx += 1

    if data_inicio:
        conditions.append(f"data_publicacao >= ${idx}")
        args.append(_parse_ts(data_inicio))
        idx += 1

    if data_fim:
        # +1 day para incluir o dia inteiro
        conditions.append(f"data_publicacao < ${idx}::timestamptz + interval '1 day'")
        args.append(_parse_ts(data_fim))
        idx += 1

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    count_sql = f"SELECT COUNT(*) FROM licitacoes_cache {where}"
    data_sql = f"""
        SELECT numero, id, ano, objeto, orgao_nome, orgao_cnpj, uf, municipio,
               modalidade, modalidade_codigo, modo_disputa, situacao, valor_estimado,
               data_publicacao, data_abertura, data_encerramento,
               esfera, poder, srp, numero_processo, informacao_complementar,
               amparo_legal, fonte, atualizado_em
        FROM licitacoes_cache
        {where}
        ORDER BY data_publicacao DESC NULLS LAST, atualizado_em DESC
        LIMIT ${idx} OFFSET ${idx + 1}
    """
    args_data = args + [limit, (page - 1) * limit]

    async with pool.acquire() as conn:
        total = await conn.fetchval(count_sql, *args) or 0
        rows = await conn.fetch(data_sql, *args_data)

    items = []
    for row in rows:
        d = dict(row)
        for k in ("data_publicacao", "data_abertura", "data_encerramento", "atualizado_em"):
            if d.get(k) and hasattr(d[k], "isoformat"):
                d[k] = d[k].isoformat()
        # Renomeia campos para o schema do frontend
        d["data_publicacao_pncp"] = d.pop("data_publicacao", None)
        d["criado_em"] = d.pop("atualizado_em", None)
        d["is_favoritada"] = False
        items.append(d)

    return items, int(total)
