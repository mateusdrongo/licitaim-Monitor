"""
cache_writer.py — Escreve tenders coletados na licitacoes_cache e detecta
                  mudanças em licitações favoritadas para notificar usuários.

Fluxo por ciclo de coleta:
  scraper → tenders normalizados → upsert_to_licitacoes_cache()
                                    ↓ changed_tenders
                                 notify_favorites_changes()
                                    ↓ insere alertas + notifications no DB
                                 (check_all_monitors no scheduler da API
                                  já cobre novas licitações × robôs a cada 15min)
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime
from typing import Optional

import asyncpg

logger = logging.getLogger("collector.cache_writer")

# ── Mapeamento modalidade → código (mesmo que licitacoes_repo.py) ─────────────
_MODAL_MAP: dict[str, int] = {
    "pregão eletrônico": 6,
    "pregão presencial": 5,
    "concorrência": 1,
    "tomada de preços": 2,
    "convite": 3,
    "concurso": 4,
    "leilão": 7,
    "diálogo competitivo": 8,
    "pré-qualificação": 9,
    "manifestação de interesse": 10,
    "rdc eletrônico": 11,
    "rdc presencial": 12,
    "dispensa": 13,
    "credenciamento": 14,
    "inexigibilidade": 15,
}


def _modal_code(name: Optional[str]) -> Optional[int]:
    if not name:
        return None
    lower = name.lower().strip()
    for k, v in _MODAL_MAP.items():
        if k in lower:
            return v
    return None


def _parse_ts(val) -> Optional[datetime]:
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day)
    s = str(val).strip().replace("Z", "")
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(s[: len(fmt)], fmt)
        except ValueError:
            continue
    return None


# Campos rastreados para detecção de mudanças: (chave no dict, coluna no cache)
_CHANGE_TRACKED = (
    ("situacao",       "situacao"),
    ("valor_estimado", "valor_estimado"),
    ("modalidade",     "modalidade"),
    ("objeto",         "objeto"),
)

# SQL de upsert — idempotente, usa COALESCE para não apagar campos ricos
# que podem ter sido preenchidos por enriquecimento externo anterior.
_UPSERT_SQL = """
    INSERT INTO licitacoes_cache (
        numero, id, objeto, orgao_nome, orgao_cnpj, uf, municipio,
        modalidade, modalidade_codigo, modo_disputa, situacao,
        valor_estimado, data_publicacao, data_abertura, data_encerramento,
        esfera, poder, srp, numero_processo, informacao_complementar,
        amparo_legal, raw_json, fonte, atualizado_em
    ) VALUES (
        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,
        $16,$17,$18,$19,$20,$21,$22,$23,NOW()
    )
    ON CONFLICT (numero) DO UPDATE SET
        id                      = EXCLUDED.id,
        objeto                  = COALESCE(EXCLUDED.objeto,         licitacoes_cache.objeto),
        orgao_nome              = COALESCE(EXCLUDED.orgao_nome,     licitacoes_cache.orgao_nome),
        orgao_cnpj              = COALESCE(EXCLUDED.orgao_cnpj,     licitacoes_cache.orgao_cnpj),
        uf                      = COALESCE(EXCLUDED.uf,             licitacoes_cache.uf),
        municipio               = COALESCE(EXCLUDED.municipio,      licitacoes_cache.municipio),
        modalidade              = COALESCE(EXCLUDED.modalidade,     licitacoes_cache.modalidade),
        modalidade_codigo       = COALESCE(EXCLUDED.modalidade_codigo, licitacoes_cache.modalidade_codigo),
        modo_disputa            = COALESCE(EXCLUDED.modo_disputa,   licitacoes_cache.modo_disputa),
        situacao                = COALESCE(EXCLUDED.situacao,       licitacoes_cache.situacao),
        valor_estimado          = COALESCE(EXCLUDED.valor_estimado, licitacoes_cache.valor_estimado),
        data_publicacao         = COALESCE(EXCLUDED.data_publicacao, licitacoes_cache.data_publicacao),
        data_abertura           = COALESCE(EXCLUDED.data_abertura,  licitacoes_cache.data_abertura),
        data_encerramento       = COALESCE(EXCLUDED.data_encerramento, licitacoes_cache.data_encerramento),
        esfera                  = COALESCE(EXCLUDED.esfera,         licitacoes_cache.esfera),
        poder                   = COALESCE(EXCLUDED.poder,          licitacoes_cache.poder),
        srp                     = EXCLUDED.srp,
        numero_processo         = COALESCE(EXCLUDED.numero_processo, licitacoes_cache.numero_processo),
        informacao_complementar = COALESCE(EXCLUDED.informacao_complementar, licitacoes_cache.informacao_complementar),
        amparo_legal            = COALESCE(EXCLUDED.amparo_legal,   licitacoes_cache.amparo_legal),
        raw_json                = EXCLUDED.raw_json,
        fonte                   = EXCLUDED.fonte,
        atualizado_em           = NOW()
    RETURNING (xmax = 0) AS inserted
"""


def _to_cache_row(t: dict, fonte: str) -> Optional[dict]:
    """
    Transforma um tender normalizado pelo TenderProcessor para o schema de
    licitacoes_cache. Retorna None se não houver número de controle (PK obrigatória).
    """
    numero = (
        t.get("numero_controle")
        or t.get("external_id")
        or t.get("id")
        or t.get("numero")
    )
    if not numero:
        return None

    return {
        "numero":                 str(numero),
        "id":                     str(t.get("external_id") or numero),
        "objeto":                 t.get("objeto"),
        "orgao_nome":             t.get("orgao") or t.get("orgao_nome"),
        "orgao_cnpj":             t.get("orgao_cnpj") or t.get("cnpj"),
        "uf":                     t.get("uf"),
        "municipio":              t.get("municipio"),
        "modalidade":             t.get("modalidade"),
        "modalidade_codigo":      _modal_code(t.get("modalidade")),
        "modo_disputa":           t.get("modo_disputa"),
        "situacao":               t.get("situacao"),
        "valor_estimado":         (
            float(t["valor_estimado"]) if t.get("valor_estimado") is not None else None
        ),
        "data_publicacao":        _parse_ts(
            t.get("data_publicacao") or t.get("data_abertura")
        ),
        "data_abertura":          _parse_ts(t.get("data_abertura")),
        "data_encerramento":      _parse_ts(t.get("data_encerramento")),
        "esfera":                 t.get("esfera"),
        "poder":                  t.get("poder"),
        "srp":                    bool(t.get("srp", False)),
        "numero_processo":        t.get("numero_processo"),
        "informacao_complementar": t.get("informacao_complementar"),
        "amparo_legal":           t.get("amparo_legal"),
        "raw_json":               json.dumps(
            {k: v for k, v in t.items() if v is not None}, default=str
        ),
        "fonte":                  fonte,
    }


async def upsert_to_licitacoes_cache(
    pool: asyncpg.Pool,
    tenders: list[dict],
    fonte: str = "collector",
    batch_size: int = 50,
) -> tuple[int, int, list[dict]]:
    """
    Recebe lista de tenders normalizados (saída do TenderProcessor._normalize),
    faz upsert em licitacoes_cache e retorna (inseridos, atualizados, changed_tenders).

    changed_tenders: lista de dicts que incluem um campo '_changes'
    {campo: (valor_antigo, valor_novo)} para uso em notificações.
    """
    if not tenders:
        return 0, 0, []

    rows = [_to_cache_row(t, fonte) for t in tenders]
    rows = [r for r in rows if r]

    if not rows:
        return 0, 0, []

    inseridos = 0
    atualizados = 0
    changed_tenders: list[dict] = []

    # Processa em lotes para não manter transação longa
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        numeros = [r["numero"] for r in batch]

        async with pool.acquire() as conn:
            # Pre-fetch snapshots para detecção de mudanças
            existing: dict[str, dict] = {}
            try:
                prefetch = await conn.fetch(
                    """SELECT numero, situacao,
                              valor_estimado::text AS valor_estimado,
                              modalidade, objeto
                         FROM licitacoes_cache
                        WHERE numero = ANY($1::text[])""",
                    numeros,
                )
                existing = {r["numero"]: dict(r) for r in prefetch}
            except Exception as exc:
                logger.warning("upsert_to_licitacoes_cache pre-fetch: %s", exc)

            for row in batch:
                try:
                    result = await conn.fetchrow(
                        _UPSERT_SQL,
                        row["numero"], row["id"], row["objeto"], row["orgao_nome"],
                        row["orgao_cnpj"], row["uf"], row["municipio"],
                        row["modalidade"], row["modalidade_codigo"], row["modo_disputa"],
                        row["situacao"], row["valor_estimado"],
                        row["data_publicacao"], row["data_abertura"], row["data_encerramento"],
                        row["esfera"], row["poder"], row["srp"],
                        row["numero_processo"], row["informacao_complementar"],
                        row["amparo_legal"], row["raw_json"], row["fonte"],
                    )
                    was_inserted = bool(result and result["inserted"])
                    if was_inserted:
                        inseridos += 1
                    else:
                        atualizados += 1
                        old = existing.get(row["numero"])
                        if old:
                            diffs: dict = {}
                            for ikey, ckey in _CHANGE_TRACKED:
                                new_val = row.get(ikey)
                                old_val = old.get(ckey)
                                if new_val is not None and old_val is not None:
                                    if str(new_val).strip() != str(old_val).strip():
                                        diffs[ikey] = (str(old_val), str(new_val))
                            if diffs:
                                changed_tenders.append({**row, "_changes": diffs})
                except Exception as exc:
                    logger.warning(
                        "upsert_to_licitacoes_cache skip '%s': %s", row["numero"], exc
                    )

    logger.info(
        "upsert_to_licitacoes_cache: %d inseridos, %d atualizados, %d com mudanças.",
        inseridos, atualizados, len(changed_tenders),
    )
    return inseridos, atualizados, changed_tenders


async def notify_favorites_changes(
    pool: asyncpg.Pool,
    changed_tenders: list[dict],
) -> None:
    """
    Para cada tender com mudanças detectadas, verifica usuários que o favoritaram
    e insere alertas em `alertas` e `notifications` (in-app / WebSocket).

    A entrega por e-mail e Telegram é feita pelo scheduler da API (send_tender_update),
    que lê os alertas novos e os despacha pelos canais habilitados.
    Aqui apenas persistimos o alerta com dedup_key de 5 minutos para evitar
    duplicatas entre ciclos consecutivos.
    """
    if not changed_tenders:
        return

    notified = 0
    for tender in changed_tenders:
        numero   = tender.get("numero", "")
        tid      = tender.get("id") or numero
        changes  = tender.get("_changes", {})
        if not changes or not numero:
            continue

        objeto = (tender.get("objeto") or "")[:150]
        changes_str = "\n".join(
            f"  • {campo}: {ant} → {novo}"
            for campo, (ant, novo) in changes.items()
        )
        title = f"⚠️ Licitação atualizada: {objeto[:60]}"
        body  = (
            f"A licitação a seguir teve alterações:\n\n{objeto}"
            f"\n\nMudanças:\n{changes_str}"
        )

        try:
            favs = await pool.fetch(
                """SELECT user_id FROM favoritos
                   WHERE licitacao_id = $1 OR licitacao_id = $2""",
                numero, tid,
            )
        except Exception as exc:
            logger.warning("notify_favorites_changes fetch favs (%s): %s", numero, exc)
            continue

        if not favs:
            continue

        bucket = int(time.time() // 300)
        for fav in favs:
            user_id   = str(fav["user_id"])
            dedup_key = f"coll:{user_id}:{numero[:64]}:{bucket}"
            try:
                await pool.execute(
                    """INSERT INTO alertas
                       (user_id, tipo, titulo, descricao,
                        licitacao_id, licitacao_objeto, lido, dedup_key)
                       VALUES ($1,'situacao_alterada',$2,$3,$4,$5,false,$6)
                       ON CONFLICT (dedup_key)
                       WHERE dedup_key IS NOT NULL DO NOTHING""",
                    user_id, title, body,
                    numero, objeto or None,
                    dedup_key,
                )
                # In-app notification lida pelo WebSocket na reconexão
                await pool.execute(
                    """INSERT INTO notifications
                       (user_id, title, body, tipo, channel, lida)
                       VALUES ($1,$2,$3,'update','push',false)""",
                    user_id, title, body,
                )
                notified += 1
            except Exception as exc:
                logger.warning(
                    "notify_favorites_changes user=%s tender=%s: %s",
                    user_id, numero, exc,
                )

    if notified:
        logger.info(
            "notify_favorites_changes: %d alertas inseridos (%d tenders).",
            notified, len(changed_tenders),
        )


async def record_coverage(
    pool: asyncpg.Pool,
    total: int,
    data_ini: str,
    data_fim: str,
    is_complete: bool = True,
) -> None:
    """
    Registra cobertura do ciclo em licitacoes_cache_coverage para que a API
    saiba que o banco é autoritativo para este intervalo de datas.
    """
    try:
        scope_key = f"collector:{data_ini}:{data_fim}"
        await pool.execute(
            """INSERT INTO licitacoes_cache_coverage
               (scope_key, last_sync, total_found, is_complete)
               VALUES ($1, NOW(), $2, $3)
               ON CONFLICT (scope_key) DO UPDATE
                   SET last_sync    = NOW(),
                       total_found  = EXCLUDED.total_found,
                       is_complete  = EXCLUDED.is_complete""",
            scope_key, total, is_complete,
        )
    except Exception as exc:
        logger.warning("record_coverage: %s", exc)
