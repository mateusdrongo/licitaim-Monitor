from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
from ..core.deps import get_current_user
from ..db.session import get_pool

router = APIRouter(prefix="/monitoramentos", tags=["monitoramentos"])


from typing import Union

_ValorField = Optional[Union[str, float, int]]


def _valor_to_str(v: _ValorField) -> Optional[str]:
    """Normaliza valorMin/valorMax para string (formato usado no banco)."""
    if v is None:
        return None
    return str(v)


class MonitoramentoCreate(BaseModel):
    nome: str
    palavrasChave: list[str] = []
    modalidades: list[str] = []
    ufs: list[str] = []
    esferas: list[str] = []
    valorMin: _ValorField = None
    valorMax: _ValorField = None


class MonitoramentoUpdate(BaseModel):
    nome: Optional[str] = None
    palavrasChave: Optional[list[str]] = None
    modalidades: Optional[list[str]] = None
    ufs: Optional[list[str]] = None
    esferas: Optional[list[str]] = None
    valorMin: _ValorField = None
    valorMax: _ValorField = None
    ativo: Optional[bool] = None


def _fmt(row: dict) -> dict:
    d = dict(row)
    d["criadoEm"] = d.pop("criado_em").isoformat() if d.get("criado_em") else None
    d["atualizadoEm"] = d.pop("atualizado_em").isoformat() if d.get("atualizado_em") else None
    d["ultimaExecucao"] = d.pop("ultima_execucao").isoformat() if d.get("ultima_execucao") else None
    # parse JSON arrays stored as text
    for k in ("palavras_chave", "modalidades", "ufs", "esferas"):
        if isinstance(d.get(k), str):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                d[k] = []
    return d


@router.get("")
async def list_monitoramentos(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT id, nome, ativo, palavras_chave, modalidades, ufs, esferas,
                  valor_min, valor_max, total_alertas, ultima_execucao, criado_em, atualizado_em
           FROM monitoramentos WHERE user_id=$1 ORDER BY criado_em DESC""",
        current_user["id"],
    )
    return [_fmt(dict(r)) for r in rows]


@router.post("", status_code=201)
async def create_monitoramento(body: MonitoramentoCreate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    row = await pool.fetchrow(
        """INSERT INTO monitoramentos
           (user_id, nome, palavras_chave, modalidades, ufs, esferas, valor_min, valor_max)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
           RETURNING id, nome, ativo, palavras_chave, modalidades, ufs, esferas,
                     valor_min, valor_max, total_alertas, ultima_execucao, criado_em, atualizado_em""",
        current_user["id"], body.nome,
        json.dumps(body.palavrasChave), json.dumps(body.modalidades),
        json.dumps(body.ufs), json.dumps(body.esferas),
        _valor_to_str(body.valorMin), _valor_to_str(body.valorMax),
    )
    return _fmt(dict(row))


@router.get("/{mon_id}")
async def get_monitoramento(mon_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM monitoramentos WHERE id=$1 AND user_id=$2", mon_id, current_user["id"]
    )
    if not row:
        raise HTTPException(status_code=404, detail="Não encontrado")
    return _fmt(dict(row))


@router.put("/{mon_id}")
async def update_monitoramento(mon_id: int, body: MonitoramentoUpdate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    existing = await pool.fetchrow(
        "SELECT * FROM monitoramentos WHERE id=$1 AND user_id=$2", mon_id, current_user["id"]
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Não encontrado")

    fields = []
    values = []
    idx = 1

    if body.nome is not None:
        fields.append(f"nome=${idx}"); values.append(body.nome); idx += 1
    if body.palavrasChave is not None:
        fields.append(f"palavras_chave=${idx}"); values.append(json.dumps(body.palavrasChave)); idx += 1
    if body.modalidades is not None:
        fields.append(f"modalidades=${idx}"); values.append(json.dumps(body.modalidades)); idx += 1
    if body.ufs is not None:
        fields.append(f"ufs=${idx}"); values.append(json.dumps(body.ufs)); idx += 1
    if body.esferas is not None:
        fields.append(f"esferas=${idx}"); values.append(json.dumps(body.esferas)); idx += 1
    if body.valorMin is not None:
        fields.append(f"valor_min=${idx}"); values.append(_valor_to_str(body.valorMin)); idx += 1
    if body.valorMax is not None:
        fields.append(f"valor_max=${idx}"); values.append(_valor_to_str(body.valorMax)); idx += 1
    if body.ativo is not None:
        fields.append(f"ativo=${idx}"); values.append(body.ativo); idx += 1

    if not fields:
        return _fmt(dict(existing))

    values.extend([mon_id, current_user["id"]])
    row = await pool.fetchrow(
        f"UPDATE monitoramentos SET {', '.join(fields)} WHERE id=${idx} AND user_id=${idx+1} RETURNING *",
        *values,
    )
    return _fmt(dict(row))


@router.delete("/{mon_id}", status_code=204)
async def delete_monitoramento(mon_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    r = await pool.execute(
        "DELETE FROM monitoramentos WHERE id=$1 AND user_id=$2", mon_id, current_user["id"]
    )
    if r == "DELETE 0":
        raise HTTPException(status_code=404, detail="Não encontrado")


@router.post("/{mon_id}/toggle")
async def toggle_monitoramento(mon_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    row = await pool.fetchrow(
        "UPDATE monitoramentos SET ativo=NOT ativo WHERE id=$1 AND user_id=$2 RETURNING id, ativo",
        mon_id, current_user["id"],
    )
    if not row:
        raise HTTPException(status_code=404, detail="Não encontrado")
    return {"id": row["id"], "ativo": row["ativo"]}
