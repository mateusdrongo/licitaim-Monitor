"""
MonitorWorker — verifica monitores, tenders futuros e certidões.

check_all_monitors():        para cada monitor ativo, busca novos tenders no cache
                             desde last_checked_at e notifica usuários.
check_upcoming_tenders():    alerta 24h antes da abertura de licitações favoritas.
check_document_expirations(): alerta vencimento de certidões.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger("licitaim.monitor_worker")


# ── Shared notif-fallback helper ──────────────────────────────────────────────

_NOTIF_DEFAULTS = dict(
    notif_email=True, notif_push=True,
    notif_whatsapp=False, notif_telegram=False,
    telegram_chat_id=None, phone=None,
)


async def _fetch_with_notif_fallback(
    pool,
    full_query: str,
    fallback_query: str,
    args: tuple,
    context: str,
) -> list:
    """
    Executa full_query (que inclui colunas de notificação no JOIN com users).
    Se falhar (coluna ausente ou outro erro de schema), executa fallback_query
    (sem essas colunas) e mescla _NOTIF_DEFAULTS em cada linha.

    Parâmetros
    ----------
    pool           : asyncpg pool
    full_query     : SQL completo, com colunas notif_* de users
    fallback_query : SQL sem colunas notif_*, apenas email/nome
    args           : argumentos posicionais para ambas as queries
    context        : nome da função chamadora, usado no log de aviso
    """
    try:
        return list(await pool.fetch(full_query, *args))
    except Exception as exc:
        logger.warning(
            "%s: colunas de notificação indisponíveis, usando preferências padrão: %s",
            context, exc,
        )
        rows = await pool.fetch(fallback_query, *args)
        return [dict(r, **_NOTIF_DEFAULTS) for r in rows]


# ── Busca no cache local ──────────────────────────────────────────────────────

async def _search_cache(
    pool,
    palavras: list[str],
    modalidades: list[str],
    ufs: list[str],
    valor_min: float | None,
    valor_max: float | None,
    since: datetime,
    limit: int = 20,
) -> list[dict]:
    """
    Busca licitações no licitacoes_cache que correspondem aos critérios do monitor.
    Usa ILIKE para busca de texto simples (sem ES).
    """
    # data_publicacao é timestamptz — passa com timezone
    conditions = ["data_publicacao >= $1"]
    values: list = [since]
    idx = 2

    # Palavras-chave: OR entre todas, buscando em objeto e orgao_nome
    if palavras:
        kw_parts = []
        for p in palavras:
            pat = f"%{p.lower()}%"
            kw_parts.append(
                f"(LOWER(objeto) LIKE ${idx} OR LOWER(orgao_nome) LIKE ${idx})"
            )
            values.append(pat)
            idx += 1
        conditions.append(f"({' OR '.join(kw_parts)})")

    if modalidades:
        conditions.append(f"modalidade = ANY(${idx}::text[])")
        values.append(modalidades)
        idx += 1

    if ufs:
        conditions.append(f"uf = ANY(${idx}::text[])")
        values.append(ufs)
        idx += 1

    if valor_min is not None:
        conditions.append(f"valor_estimado >= ${idx}")
        values.append(valor_min)
        idx += 1

    if valor_max is not None:
        conditions.append(f"valor_estimado <= ${idx}")
        values.append(valor_max)
        idx += 1

    where = " AND ".join(conditions)
    rows = await pool.fetch(
        f"""SELECT numero, objeto, orgao_nome, uf, modalidade,
                   valor_estimado, data_abertura, data_publicacao
            FROM licitacoes_cache
            WHERE {where}
            ORDER BY data_publicacao DESC
            LIMIT {limit}""",
        *values,
    )
    return [
        {
            "id":             r["numero"],
            "external_id":    r["numero"],
            "objeto":         r["objeto"] or "",
            "orgao":          r["orgao_nome"] or "",
            "uf":             r["uf"] or "",
            "modalidade":     r["modalidade"] or "",
            "valorEstimado":  float(r["valor_estimado"]) if r["valor_estimado"] else None,
            "valor_estimado": float(r["valor_estimado"]) if r["valor_estimado"] else None,
            "dataAbertura":   r["data_abertura"].isoformat() if r["data_abertura"] else None,
        }
        for r in rows
    ]


# ── check_all_monitors ────────────────────────────────────────────────────────

async def check_all_monitors() -> dict:
    """
    Executa verificação de todos os monitores ativos.
    Para cada monitor: busca no cache local, notifica e atualiza timestamps.
    """
    from ..db.session import get_pool
    from .notification_service import send_monitor_match

    pool = await get_pool()
    now       = datetime.now(timezone.utc)
    # ultima_execucao é timestamp WITHOUT time zone; last_checked_at é timestamptz
    now_naive = now.replace(tzinfo=None)

    monitors = await _fetch_with_notif_fallback(
        pool,
        full_query="""
            SELECT m.id, m.user_id, m.nome, m.palavras_chave, m.modalidades,
                   m.ufs, m.valor_min, m.valor_max, m.last_checked_at,
                   u.email, u.nome AS user_nome, u.notif_email, u.notif_push,
                   u.notif_whatsapp, u.notif_telegram,
                   u.telegram_chat_id, u.phone
               FROM monitoramentos m
               JOIN users u ON u.id = m.user_id
               WHERE m.ativo = true
        """,
        fallback_query="""
            SELECT m.id, m.user_id, m.nome, m.palavras_chave, m.modalidades,
                   m.ufs, m.valor_min, m.valor_max, m.last_checked_at,
                   u.email, u.nome AS user_nome
               FROM monitoramentos m
               JOIN users u ON u.id = m.user_id
               WHERE m.ativo = true
        """,
        args=(),
        context="check_all_monitors",
    )

    total_matches   = 0
    total_monitors  = len(monitors)

    for mon in monitors:
        try:
            matches = await _check_single_monitor(mon, pool, now)
            total_matches += matches
        except Exception as exc:
            logger.warning("check_all_monitors[%d]: %s", mon["id"], exc)
        finally:
            # Sempre marca que verificou, mesmo que a busca tenha falhado
            try:
                await pool.execute(
                    """UPDATE monitoramentos
                       SET last_checked_at=$1, ultima_execucao=$2
                       WHERE id=$3""",
                    now, now_naive, mon["id"],
                )
            except Exception as upd_exc:
                logger.warning("check_all_monitors[%d] update timestamp: %s", mon["id"], upd_exc)

    logger.info(
        "check_all_monitors: %d monitores verificados, %d matches encontrados.",
        total_monitors, total_matches,
    )
    return {"monitors_checked": total_monitors, "matches_found": total_matches}


async def _check_single_monitor(mon, pool, now: datetime) -> int:
    """Verifica um monitor individual via cache DB e envia notificações."""
    from .notification_service import send_monitor_match

    last_checked = mon["last_checked_at"]
    # Na primeira execução, olha 30 dias atrás para cobrir todo o cache atual.
    # Nas execuções seguintes, usa o último timestamp verificado.
    since = last_checked or (now - timedelta(days=30))
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    def _parse_json_list(val) -> list[str]:
        if not val:
            return []
        if isinstance(val, list):
            return val
        try:
            return json.loads(val)
        except Exception:
            return []

    palavras    = _parse_json_list(mon["palavras_chave"])
    modalidades = _parse_json_list(mon["modalidades"])
    ufs         = _parse_json_list(mon["ufs"])

    # Valor — armazenado como text, converte para float
    def _to_float(v) -> float | None:
        try:
            return float(v) if v else None
        except (ValueError, TypeError):
            return None

    valor_min = _to_float(mon["valor_min"])
    valor_max = _to_float(mon["valor_max"])

    # Busca no cache local
    tenders = await _search_cache(
        pool, palavras, modalidades, ufs, valor_min, valor_max, since
    )

    if not tenders:
        return 0

    user = {
        "id":                mon["user_id"],
        "email":             mon["email"],
        "nome":              mon["user_nome"],
        "notif_email":       mon["notif_email"],
        "notif_push":        mon["notif_push"],
        "notif_whatsapp":    mon["notif_whatsapp"],
        "notif_telegram":    mon["notif_telegram"],
        "telegram_chat_id":  mon["telegram_chat_id"],
        "phone":             mon["phone"],
    }
    monitor_dict = {
        "id":   mon["id"],
        "nome": mon["nome"],
    }

    # Deduplica: não re-notifica o mesmo tender para o mesmo monitor
    tender_ids = [str(t["id"]) for t in tenders]
    already_alerted = await pool.fetch(
        """SELECT licitacao_id FROM alertas
           WHERE user_id=$1 AND tipo='nova_licitacao'
             AND monitoramento_id=$2
             AND licitacao_id = ANY($3::text[])""",
        str(mon["user_id"]),
        mon["id"],
        tender_ids,
    )
    already_ids = {r["licitacao_id"] for r in already_alerted}

    sent = 0
    for tender in tenders:
        tid = str(tender["id"])
        if tid in already_ids:
            continue
        await send_monitor_match(user, monitor_dict, tender)
        sent += 1

    return sent


# ── check_upcoming_tenders ────────────────────────────────────────────────────

async def check_upcoming_tenders() -> dict:
    """
    Alerta usuários sobre licitações favoritas que abrem nas próximas 24h.
    Usa licitacoes_cache + favoritos (sem depender do ES).
    """
    from ..db.session import get_pool
    from .notification_service import send_document_expiration, send

    pool  = await get_pool()
    now   = datetime.now(timezone.utc)
    hoje  = now.date()
    amanha = hoje + timedelta(days=1)

    # Licitações que abrem amanhã (ou hoje) no cache
    upcoming = await pool.fetch(
        """SELECT numero, objeto, orgao_nome, uf, data_abertura
           FROM licitacoes_cache
           WHERE data_abertura::date BETWEEN $1 AND $2
             AND data_abertura IS NOT NULL""",
        hoje, amanha,
    )

    if not upcoming:
        logger.info("check_upcoming_tenders: sem licitações abrindo nas próximas 24h.")
        return {"tenders_checked": 0, "notifications_sent": 0, "notifications_skipped": 0}

    tender_numeros = [r["numero"] for r in upcoming]

    # Usuários que favoritaram essas licitações
    # favoritos.licitacao_id armazena o numero PNCP
    favs = await _fetch_with_notif_fallback(
        pool,
        full_query="""
            SELECT f.user_id, f.licitacao_id,
                   u.email, u.nome, u.notif_email, u.notif_push,
                   u.notif_whatsapp, u.notif_telegram,
                   u.telegram_chat_id, u.phone
               FROM favoritos f
               JOIN users u ON u.id = f.user_id
               WHERE f.licitacao_id = ANY($1::text[])
        """,
        fallback_query="""
            SELECT f.user_id, f.licitacao_id, u.email, u.nome
               FROM favoritos f
               JOIN users u ON u.id = f.user_id
               WHERE f.licitacao_id = ANY($1::text[])
        """,
        args=(tender_numeros,),
        context="check_upcoming_tenders",
    )

    tender_map = {r["numero"]: r for r in upcoming}

    # ── Deduplicação em lote ────────────────────────────────────────────────
    # Coleta pares (user_id, licitacao_id) que já têm um alerta 'warning'
    # nas últimas 24h para evitar reenvio quando o job rodar mais de uma vez no dia.
    fav_user_ids     = [str(fav["user_id"])    for fav in favs]
    fav_licitacao_ids = [fav["licitacao_id"]   for fav in favs]

    already_sent_rows = await pool.fetch(
        """SELECT user_id, licitacao_id FROM alertas
           WHERE tipo         = 'warning'
             AND user_id      = ANY($1::text[])
             AND licitacao_id = ANY($2::text[])
             AND criado_em    > NOW() - INTERVAL '24 hours'""",
        fav_user_ids, fav_licitacao_ids,
    )
    already_sent = {(r["user_id"], r["licitacao_id"]) for r in already_sent_rows}

    sent    = 0
    skipped = 0

    for fav in favs:
        numero  = fav["licitacao_id"]
        tender  = tender_map.get(numero)
        if not tender:
            continue

        user_id_str = str(fav["user_id"])

        # Pula se já alertado hoje para este usuário + licitação
        if (user_id_str, numero) in already_sent:
            skipped += 1
            logger.debug(
                "check_upcoming_tenders: user=%s licitacao=%s já alertado — pulando.",
                user_id_str, numero,
            )
            continue

        abertura = tender["data_abertura"].strftime("%d/%m/%Y %H:%M") if tender["data_abertura"] else ""
        objeto   = (tender["objeto"] or "")[:120]

        title = "⏰ Licitação abre em 24h"
        body  = (
            f"Uma licitação que você favoritou abre em breve!\n\n"
            f"Objeto: {objeto}\n"
            f"Abertura: {abertura}"
        )

        # Persiste alerta em `alertas` — necessário tanto para exibição na UI
        # quanto para a deduplicação em execuções futuras do job no mesmo dia.
        try:
            await pool.execute(
                """INSERT INTO alertas
                   (user_id, tipo, titulo, descricao, licitacao_id, lido)
                   VALUES ($1,'warning',$2,$3,$4,false)""",
                user_id_str, title, body, numero,
            )
        except Exception as exc:
            logger.warning(
                "check_upcoming_tenders: erro ao persistir alerta user=%s licitacao=%s: %s",
                user_id_str, numero, exc,
            )

        user = {
            "id":               fav["user_id"],
            "email":            fav["email"],
            "nome":             fav["nome"],
            "notif_email":      fav["notif_email"],
            "notif_push":       fav["notif_push"],
            "notif_whatsapp":   fav["notif_whatsapp"],
            "notif_telegram":   fav["notif_telegram"],
            "telegram_chat_id": fav["telegram_chat_id"],
            "phone":            fav["phone"],
        }

        await send(
            user,
            title=title,
            body=body,
            tipo="warning",
            metadata={"licitacao_numero": numero},
            cta_url="https://licitaim.com.br/licitacoes",
            cta_label="Ver licitação",
        )
        sent += 1

    logger.info(
        "check_upcoming_tenders: %d notificações enviadas | %d ignoradas (dedup).",
        sent, skipped,
    )
    return {
        "tenders_checked":      len(upcoming),
        "notifications_sent":   sent,
        "notifications_skipped": skipped,
    }


# ── check_document_expirations ────────────────────────────────────────────────

async def check_document_expirations() -> dict:
    """
    Verifica certidões a vencer e envia alertas.
    Janelas: vencidas, 1d, 3d, 7d, 15d, 30d.
    """
    from ..db.session import get_pool
    from .notification_service import send_document_expiration

    pool = await get_pool()
    hoje = date.today()

    certs = await _fetch_with_notif_fallback(
        pool,
        full_query="""
            SELECT c.id, c.nome, c.tipo, c.data_vencimento, c.user_id,
                   u.email, u.nome AS user_nome, u.notif_email, u.notif_push,
                   u.notif_whatsapp, u.notif_telegram,
                   u.telegram_chat_id, u.phone
               FROM certidoes c
               JOIN users u ON u.id = c.user_id
               WHERE c.data_vencimento IS NOT NULL
                 AND c.data_vencimento >= $1
                 AND c.data_vencimento <= $2
        """,
        fallback_query="""
            SELECT c.id, c.nome, c.tipo, c.data_vencimento, c.user_id,
                   u.email, u.nome AS user_nome
               FROM certidoes c
               JOIN users u ON u.id = c.user_id
               WHERE c.data_vencimento IS NOT NULL
                 AND c.data_vencimento >= $1
                 AND c.data_vencimento <= $2
        """,
        args=(hoje - timedelta(days=1), hoje + timedelta(days=30)),
        context="check_document_expirations",
    )

    ALERT_THRESHOLDS = {30, 15, 7, 3, 1, 0, -1}
    sent     = 0
    skipped  = 0

    for cert in certs:
        dv   = cert["data_vencimento"]
        dias = (dv - hoje).days

        if dias not in ALERT_THRESHOLDS:
            continue

        # Chave de deduplicação: cert + threshold — evita reenvio se o job rodar >1× no dia
        ref_key = f"certidao_{cert['id']}_d{dias}"

        try:
            # Deduplicação: não re-alerta se já existe registro nas últimas 24h
            existing = await pool.fetchval(
                """
                SELECT id FROM alertas
                WHERE user_id      = $1
                  AND tipo         = 'prazo_vencendo'
                  AND licitacao_id = $2
                  AND criado_em    > NOW() - INTERVAL '24 hours'
                LIMIT 1
                """,
                str(cert["user_id"]), ref_key,
            )
            if existing:
                skipped += 1
                logger.debug(
                    "check_document_expirations: cert %d dias=%d já alertado — pulando.",
                    cert["id"], dias,
                )
                continue

            user = {
                "id":               cert["user_id"],
                "email":            cert["email"],
                "nome":             cert["user_nome"],
                "notif_email":      cert["notif_email"],
                "notif_push":       cert["notif_push"],
                "notif_whatsapp":   cert["notif_whatsapp"],
                "notif_telegram":   cert["notif_telegram"],
                "telegram_chat_id": cert["telegram_chat_id"],
                "phone":            cert["phone"],
            }
            certidao = {
                "id":              cert["id"],
                "nome":            cert["nome"],
                "tipo":            cert["tipo"],
                "data_vencimento": dv.isoformat(),
            }

            await send_document_expiration(user, certidao, dias, ref_key=ref_key)
            sent += 1
        except Exception as exc:
            logger.warning(
                "check_document_expirations: erro ao processar cert %d: %s",
                cert["id"], exc,
            )

    # Registra execução na tabela job_runs (usada pelo startup para detectar misfires).
    # Gravado após processar todos os certificados — mesmo que alguns falhem individualmente,
    # o job é considerado executado para fins de misfire-recovery.
    try:
        await pool.execute(
            "INSERT INTO job_runs (job_name) VALUES ($1)",
            "check_document_expirations",
        )
    except Exception as exc:
        logger.warning("check_document_expirations: falha ao registrar job_run: %s", exc)

    logger.info(
        "check_document_expirations: %d alertas enviados | %d ignorados (dedup).",
        sent, skipped,
    )
    return {"certidoes_checked": len(certs), "alerts_sent": sent, "alerts_skipped": skipped}
