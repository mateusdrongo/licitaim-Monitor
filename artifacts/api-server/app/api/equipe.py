from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..core.deps import get_current_user
from ..db.session import get_pool

router = APIRouter(prefix="/equipe", tags=["equipe"])


class MembroCreate(BaseModel):
    nome: str
    email: str
    papel: str = "visualizador"


class MembroUpdate(BaseModel):
    papel: Optional[str] = None
    status: Optional[str] = None


def _fmt(row) -> dict:
    d = dict(row)
    d["criadoEm"] = d.pop("criado_em").isoformat() if d.get("criado_em") else None
    d["atualizadoEm"] = d.pop("atualizado_em").isoformat() if d.get("atualizado_em") else None
    return d


@router.get("")
async def list_equipe(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM equipe_membros WHERE owner_id=$1 ORDER BY criado_em DESC",
        current_user["id"],
    )
    return [_fmt(dict(r)) for r in rows]


@router.post("", status_code=201)
async def add_membro(body: MembroCreate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    existing = await pool.fetchrow(
        "SELECT id FROM equipe_membros WHERE owner_id=$1 AND email=$2",
        current_user["id"], body.email,
    )
    if existing:
        raise HTTPException(status_code=409, detail="Membro já cadastrado")
    row = await pool.fetchrow(
        """INSERT INTO equipe_membros (owner_id, nome, email, papel)
           VALUES ($1,$2,$3,$4) RETURNING *""",
        current_user["id"], body.nome, body.email, body.papel,
    )
    return _fmt(dict(row))


@router.patch("/{membro_id}")
async def update_membro(membro_id: int, body: MembroUpdate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    fields, values, idx = [], [], 1
    if body.papel is not None:
        fields.append(f"papel=${idx}"); values.append(body.papel); idx += 1
    if body.status is not None:
        fields.append(f"status=${idx}"); values.append(body.status); idx += 1
    if not fields:
        row = await pool.fetchrow("SELECT * FROM equipe_membros WHERE id=$1 AND owner_id=$2", membro_id, current_user["id"])
        return _fmt(dict(row))
    values.extend([membro_id, current_user["id"]])
    row = await pool.fetchrow(
        f"UPDATE equipe_membros SET {', '.join(fields)} WHERE id=${idx} AND owner_id=${idx+1} RETURNING *",
        *values,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Não encontrado")
    return _fmt(dict(row))


@router.delete("/{membro_id}", status_code=204)
async def delete_membro(membro_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    r = await pool.execute(
        "DELETE FROM equipe_membros WHERE id=$1 AND owner_id=$2", membro_id, current_user["id"]
    )
    if r == "DELETE 0":
        raise HTTPException(status_code=404, detail="Não encontrado")
