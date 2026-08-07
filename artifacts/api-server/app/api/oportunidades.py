from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import json
from ..core.deps import get_current_user
from ..db.session import get_pool

router = APIRouter(prefix="/oportunidades", tags=["oportunidades"])


class OportunidadeCreate(BaseModel):
    titulo: str
    estagio: str = "identificada"
    valorEstimado: Optional[str] = None
    probabilidade: Optional[int] = None
    licitacaoId: Optional[str] = None
    licitacaoObjeto: Optional[str] = None
    responsavelNome: Optional[str] = None
    responsavelId: Optional[int] = None
    prazo: Optional[str] = None
    notas: Optional[str] = None
    tags: list[str] = []


class OportunidadeUpdate(BaseModel):
    titulo: Optional[str] = None
    estagio: Optional[str] = None
    valorEstimado: Optional[str] = None
    probabilidade: Optional[int] = None
    responsavelNome: Optional[str] = None
    responsavelId: Optional[int] = None
    prazo: Optional[str] = None
    notas: Optional[str] = None
    tags: Optional[list[str]] = None


def _fmt(row) -> dict:
    d = dict(row)
    d["criadoEm"] = d.pop("criado_em").isoformat() if d.get("criado_em") else None
    d["atualizadoEm"] = d.pop("atualizado_em").isoformat() if d.get("atualizado_em") else None
    if isinstance(d.get("tags"), str):
        try:
            d["tags"] = json.loads(d["tags"])
        except Exception:
            d["tags"] = []
    return d


@router.get("")
async def list_oportunidades(
    estagio: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    if estagio:
        rows = await pool.fetch(
            "SELECT * FROM oportunidades WHERE user_id=$1 AND estagio=$2 ORDER BY criado_em DESC",
            current_user["id"], estagio,
        )
    else:
        rows = await pool.fetch(
            "SELECT * FROM oportunidades WHERE user_id=$1 ORDER BY criado_em DESC",
            current_user["id"],
        )
    return [_fmt(dict(r)) for r in rows]


@router.get("/pipeline-stats")
async def pipeline_stats(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT estagio, COUNT(*) as total, SUM(CASE WHEN valor_estimado ~ '^[0-9]+(\\.?[0-9]*)$' THEN valor_estimado::numeric ELSE 0 END) as valor FROM oportunidades WHERE user_id=$1 GROUP BY estagio",
        current_user["id"],
    )
    return [{"estagio": r["estagio"], "total": r["total"], "valor": float(r["valor"] or 0)} for r in rows]


@router.post("", status_code=201)
async def create_oportunidade(body: OportunidadeCreate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    row = await pool.fetchrow(
        """INSERT INTO oportunidades
           (user_id, titulo, estagio, valor_estimado, probabilidade, licitacao_id,
            licitacao_objeto, responsavel_nome, responsavel_id, prazo, notas, tags)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) RETURNING *""",
        current_user["id"], body.titulo, body.estagio, body.valorEstimado,
        body.probabilidade, body.licitacaoId, body.licitacaoObjeto,
        body.responsavelNome, body.responsavelId, body.prazo, body.notas,
        json.dumps(body.tags),
    )
    return _fmt(dict(row))


@router.get("/{op_id}")
async def get_oportunidade(op_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM oportunidades WHERE id=$1 AND user_id=$2", op_id, current_user["id"]
    )
    if not row:
        raise HTTPException(status_code=404, detail="Não encontrado")
    return _fmt(dict(row))


@router.patch("/{op_id}")
async def update_oportunidade(op_id: int, body: OportunidadeUpdate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    col_map = [
        ("titulo","titulo"), ("estagio","estagio"), ("valorEstimado","valor_estimado"),
        ("probabilidade","probabilidade"), ("responsavelNome","responsavel_nome"),
        ("responsavelId","responsavel_id"), ("prazo","prazo"), ("notas","notas"),
    ]
    fields, values, idx = [], [], 1
    for attr, col in col_map:
        val = getattr(body, attr)
        if val is not None:
            fields.append(f"{col}=${idx}"); values.append(val); idx += 1
    if body.tags is not None:
        fields.append(f"tags=${idx}"); values.append(json.dumps(body.tags)); idx += 1

    if not fields:
        row = await pool.fetchrow("SELECT * FROM oportunidades WHERE id=$1 AND user_id=$2", op_id, current_user["id"])
        return _fmt(dict(row))
    values.extend([op_id, current_user["id"]])
    row = await pool.fetchrow(
        f"UPDATE oportunidades SET {', '.join(fields)} WHERE id=${idx} AND user_id=${idx+1} RETURNING *",
        *values,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Não encontrado")
    return _fmt(dict(row))


@router.delete("/{op_id}", status_code=204)
async def delete_oportunidade(op_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    r = await pool.execute(
        "DELETE FROM oportunidades WHERE id=$1 AND user_id=$2", op_id, current_user["id"]
    )
    if r == "DELETE 0":
        raise HTTPException(status_code=404, detail="Não encontrado")
