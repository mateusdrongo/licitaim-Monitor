from fastapi import APIRouter, Depends, Query
from typing import Optional
from ..core.deps import get_current_user
from ..db.session import get_pool

router = APIRouter(prefix="/alertas", tags=["alertas"])


def _fmt(row: dict) -> dict:
    d = dict(row)
    d["criadoEm"] = d.pop("criado_em").isoformat() if d.get("criado_em") else None
    # link pode não existir em alertas antigos (antes da migração)
    d.setdefault("link", None)
    return d


@router.get("")
async def list_alertas(
    lido: Optional[bool] = Query(None),
    tipo: Optional[str] = Query(None),
    ger_id: Optional[int] = Query(None, description="Filtra alertas do gerenciamento especificado"),
    limit: int = Query(100, le=200),
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    uid = current_user["id"]

    conditions = ["user_id=$1"]
    values: list = [uid]
    idx = 2

    if lido is not None:
        conditions.append(f"lido=${idx}"); values.append(lido); idx += 1
    if tipo:
        conditions.append(f"tipo=${idx}"); values.append(tipo); idx += 1
    if ger_id is not None:
        # Inclui alertas com link correto OU alertas sem link cujo licitacao_id
        # aponta para uma tarefa desse gerenciamento (retrocompatibilidade com
        # alertas criados antes da coluna link existir).
        conditions.append(
            f"(link=${idx}"
            f" OR (link IS NULL AND licitacao_id IN ("
            f"   SELECT 'tarefa_' || t.id::text"
            f"   FROM gerenciamento_tarefas t"
            f"   WHERE t.gerenciamento_id = ${idx + 1}"
            f")))"
        )
        values.append(f"/gerenciamento/{ger_id}")
        values.append(ger_id)
        idx += 2

    where = " AND ".join(conditions)
    rows = await pool.fetch(
        f"SELECT * FROM alertas WHERE {where} ORDER BY criado_em DESC LIMIT {limit}",
        *values,
    )

    total_nao_lidos = await pool.fetchval(
        "SELECT COUNT(*) FROM alertas WHERE user_id=$1 AND lido=false", uid
    )

    return {
        "data": [_fmt(dict(r)) for r in rows],
        "total": len(rows),
        "totalNaoLidos": int(total_nao_lidos or 0),
    }


@router.get("/por-gerenciamento")
async def count_por_gerenciamento(current_user: dict = Depends(get_current_user)):
    """Retorna contagem de alertas não lidos agrupados por gerenciamento_id (extraído do campo link)."""
    pool = await get_pool()
    uid = current_user["id"]
    rows = await pool.fetch(
        """
        SELECT link, COUNT(*) AS total
        FROM alertas
        WHERE user_id=$1 AND lido=false AND link LIKE '/gerenciamento/%'
        GROUP BY link
        """,
        uid,
    )
    result: dict[str, int] = {}
    for row in rows:
        link: str = row["link"]
        # link format: /gerenciamento/{id}
        parts = link.split("/")
        if len(parts) >= 3 and parts[-1].isdigit():
            result[parts[-1]] = int(row["total"])
    return {"data": result}


@router.get("/nao-lidos")
async def count_nao_lidos(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    count = await pool.fetchval(
        "SELECT COUNT(*) FROM alertas WHERE user_id=$1 AND lido=false", current_user["id"]
    )
    return {"count": int(count or 0)}


@router.post("/{alerta_id}/ler")
async def marcar_lido(alerta_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    await pool.execute(
        "UPDATE alertas SET lido=true WHERE id=$1 AND user_id=$2",
        alerta_id, current_user["id"],
    )
    return {"ok": True}


@router.post("/ler-todos")
async def marcar_todos_lidos(
    ger_id: Optional[int] = Query(None, description="Marca apenas alertas do gerenciamento especificado"),
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    uid = current_user["id"]
    if ger_id is not None:
        # Marca como lidos alertas com link correto OU alertas sem link cujo
        # licitacao_id aponta para uma tarefa desse gerenciamento (retrocompat.).
        await pool.execute(
            """
            UPDATE alertas SET lido=true
            WHERE user_id=$1 AND lido=false
              AND (
                link = $2
                OR (link IS NULL AND licitacao_id IN (
                    SELECT 'tarefa_' || t.id::text
                    FROM gerenciamento_tarefas t
                    WHERE t.gerenciamento_id = $3
                ))
              )
            """,
            uid, f"/gerenciamento/{ger_id}", ger_id,
        )
    else:
        await pool.execute(
            "UPDATE alertas SET lido=true WHERE user_id=$1 AND lido=false",
            uid,
        )
    return {"ok": True}
