"""
tender_change_service.py — Detecta mudanças em licitações favoritadas e dispara alertas.

Fluxo:
  1. Recebe um tender atualizado (por ex. vindo do collector ou de um sync periódico)
  2. Compara os campos rastreados com os valores em snapshot armazenados em `favoritos`
  3. Para cada usuário que favoritou a licitação e cujos dados mudaram:
     - Chama send_tender_update() com o diff
     - Atualiza o snapshot em `favoritos` para reflectir os novos valores
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("licitaim.tender_change")

# Campos rastreados: (campo_no_tender_dict, coluna_no_favoritos)
TRACKED_FIELDS: list[tuple[str, str]] = [
    ("situacao",        "licitacao_situacao"),
    ("valor_estimado",  "licitacao_valor"),
    ("modalidade",      "licitacao_modalidade"),
    ("objeto",          "licitacao_objeto"),
]

# Campos que devem ser comparados como número (evita alertas espúrios por
# representações equivalentes como "100000.00" vs "100000.0").
_NUMERIC_FIELDS: frozenset[str] = frozenset({"valor_estimado"})


def _normalize_value(raw: object, is_numeric: bool) -> str:
    """
    Normaliza um valor de campo para comparação e armazenamento de snapshot.

    Campos numéricos são convertidos para float antes de retornar a string
    representativa, de modo que "100000.00" e "100000.0" produzam o mesmo resultado.
    Campos de texto são simplesmente convertidos para string e strip()'ados.
    """
    s = str(raw or "").strip()
    if not s:
        return ""
    if is_numeric:
        try:
            return f"{float(s):.2f}"   # forma canónica de 2 casas decimais
        except (ValueError, TypeError):
            return s
    return s


def _build_diff(tender: dict, fav_row: dict) -> dict[str, tuple[str, str]]:
    """
    Compara os campos rastreados do tender com os valores armazenados no favorito.

    Campos numéricos (valor_estimado) são comparados como float para evitar alertas
    espúrios causados por representações equivalentes ("100000.00" vs "100000.0").

    Returns dict {campo: (valor_antigo, valor_novo)} contendo apenas campos alterados.
    """
    diff: dict[str, tuple[str, str]] = {}
    for tender_key, fav_col in TRACKED_FIELDS:
        is_num = tender_key in _NUMERIC_FIELDS
        new_val = _normalize_value(tender.get(tender_key), is_numeric=is_num)
        old_val = _normalize_value(fav_row.get(fav_col), is_numeric=is_num)
        if new_val and old_val != new_val:   # só considera mudança se houver novo valor
            diff[tender_key] = (old_val, new_val)
    return diff


async def notify_favorited_tender_changes(
    tender: dict,
    *,
    background_tasks=None,
) -> dict:
    """
    Detecta mudanças em uma licitação e notifica todos os usuários que a favoritaram.

    Parameters
    ----------
    tender : dict
        Dados actualizados da licitação. Deve conter pelo menos `id` (ou `numero`).
    background_tasks : BackgroundTasks | None
        Se fornecido, as notificações são enviadas em background.

    Returns
    -------
    dict com {users_checked, users_notified, users_skipped}
    """
    from ..db.session import get_pool
    import app.services.notification_service as _notif_svc

    # The frontend stores `lic.id` as licitacao_id when favoriting, but the
    # scheduler delivers changed tenders keyed by `numero` (PNCP control number).
    # For PNCP results these two fields can differ, so we query favorites that
    # match EITHER the tender's `id` OR its `numero` to avoid missing any.
    tender_id     = str(tender.get("id")     or "").strip()
    tender_numero = str(tender.get("numero") or "").strip()

    # Deduplicated list of candidate IDs (preserving order, skipping empty)
    seen_ids: dict[str, None] = {}
    for cid in [tender_id, tender_numero]:
        if cid:
            seen_ids[cid] = None
    candidate_ids: list[str] = list(seen_ids)

    if not candidate_ids:
        logger.warning("notify_favorited_tender_changes: tender sem id/numero — ignorado.")
        return {"users_checked": 0, "users_notified": 0, "users_skipped": 0}

    pool = await get_pool()

    # Busca todos os usuários que favoritaram esta licitação.
    # Usa ANY para cobrir tanto o caso em que o frontend gravou o `id` (portal ID)
    # quanto o `numero` (PNCP control number) como licitacao_id.
    rows = await pool.fetch(
        """
        SELECT f.id AS fav_id,
               f.user_id,
               f.licitacao_id,
               f.licitacao_objeto,
               f.licitacao_orgao,
               f.licitacao_uf,
               f.licitacao_modalidade,
               f.licitacao_situacao,
               f.licitacao_valor,
               u.id,
               u.email,
               u.nome,
               u.notif_push,
               u.notif_email,
               u.notif_whatsapp,
               u.notif_telegram,
               u.telegram_chat_id,
               u.phone
          FROM favoritos f
          JOIN users u ON u.id = f.user_id
         WHERE f.licitacao_id = ANY($1::text[])
        """,
        candidate_ids,
    )

    users_checked  = len(rows)
    users_notified = 0
    users_skipped  = 0

    for row in rows:
        fav_row = dict(row)
        diff = _build_diff(tender, fav_row)

        if not diff:
            users_skipped += 1
            logger.debug(
                "notify_favorited_tender_changes: user=%s licitacao=%s — sem mudanças.",
                fav_row["user_id"], candidate_ids,
            )
            continue

        user = {
            "id":               fav_row["user_id"],
            "email":            fav_row.get("email", ""),
            "nome":             fav_row.get("nome", ""),
            "notif_push":       fav_row.get("notif_push", True),
            "notif_email":      fav_row.get("notif_email", True),
            "notif_whatsapp":   fav_row.get("notif_whatsapp", False),
            "notif_telegram":   fav_row.get("notif_telegram", False),
            "telegram_chat_id": fav_row.get("telegram_chat_id", ""),
            "phone":            fav_row.get("phone", ""),
        }

        # Usa objeto atualizado para melhor legibilidade na notificação
        tender_with_obj = {
            **tender,
            "objeto": tender.get("objeto") or fav_row.get("licitacao_objeto", ""),
        }

        await _notif_svc.send_tender_update(user, tender_with_obj, diff, background_tasks=background_tasks)

        # Actualiza snapshot no favorito para próximos cycles.
        # Normaliza valor para forma canónica (2 casas decimais) para evitar que
        # "100000.0" armazenado cause diff espúrio contra "100000.00" no próximo run.
        new_situacao   = tender.get("situacao")
        _valor_raw     = tender.get("valor_estimado")
        new_valor: Optional[str]
        if _valor_raw is not None:
            try:
                new_valor = f"{float(_valor_raw):.2f}"
            except (ValueError, TypeError):
                new_valor = str(_valor_raw) or None
        else:
            new_valor = None
        new_modalidade = tender.get("modalidade")
        new_objeto     = tender.get("objeto")

        try:
            await pool.execute(
                """
                UPDATE favoritos
                   SET licitacao_situacao  = COALESCE($2, licitacao_situacao),
                       licitacao_valor     = COALESCE($3, licitacao_valor),
                       licitacao_modalidade = COALESCE($4, licitacao_modalidade),
                       licitacao_objeto    = COALESCE($5, licitacao_objeto)
                 WHERE id = $1
                """,
                fav_row["fav_id"],
                new_situacao,
                new_valor,
                new_modalidade,
                new_objeto,
            )
        except Exception as exc:
            logger.warning(
                "notify_favorited_tender_changes: falha ao actualizar snapshot fav_id=%s: %s",
                fav_row["fav_id"], exc,
            )

        users_notified += 1
        logger.info(
            "notify_favorited_tender_changes: user=%s licitacao=%s notificado, diff=%s",
            user["id"], candidate_ids, list(diff.keys()),
        )

    return {
        "users_checked":  users_checked,
        "users_notified": users_notified,
        "users_skipped":  users_skipped,
    }
