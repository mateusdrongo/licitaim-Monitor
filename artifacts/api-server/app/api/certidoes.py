from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
from ..core.deps import get_current_user
from ..db.session import get_pool

router = APIRouter(prefix="/certidoes", tags=["certidoes"])


class CertidaoCreate(BaseModel):
    nome: str
    tipo: str = "outro"
    orgaoEmissor: Optional[str] = None
    numero: Optional[str] = None
    dataEmissao: Optional[date] = None
    dataVencimento: Optional[date] = None
    descricao: Optional[str] = None


class CertidaoUpdate(BaseModel):
    nome: Optional[str] = None
    tipo: Optional[str] = None
    orgaoEmissor: Optional[str] = None
    numero: Optional[str] = None
    dataEmissao: Optional[date] = None
    dataVencimento: Optional[date] = None
    descricao: Optional[str] = None


def _status(data_venc: Optional[date]) -> str:
    if not data_venc:
        return "sem_prazo"
    today = date.today()
    if data_venc < today:
        return "vencida"
    if (data_venc - today).days <= 30:
        return "a_vencer"
    return "ativa"


def _fmt(row) -> dict:
    d = dict(row)
    d["criadoEm"] = d.pop("criado_em").isoformat() if d.get("criado_em") else None
    d["atualizadoEm"] = d.pop("atualizado_em").isoformat() if d.get("atualizado_em") else None
    d["dataEmissao"] = d["data_emissao"].isoformat() if d.get("data_emissao") else None
    d["dataVencimento"] = d["data_vencimento"].isoformat() if d.get("data_vencimento") else None
    d["status"] = _status(d.get("data_vencimento"))
    return d


@router.get("")
async def list_certidoes(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM certidoes WHERE user_id=$1 ORDER BY data_vencimento ASC NULLS LAST",
        current_user["id"],
    )
    return [_fmt(dict(r)) for r in rows]


@router.post("", status_code=201)
async def create_certidao(body: CertidaoCreate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    row = await pool.fetchrow(
        """INSERT INTO certidoes
           (user_id, nome, tipo, orgao_emissor, numero, data_emissao, data_vencimento, descricao)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *""",
        current_user["id"], body.nome, body.tipo, body.orgaoEmissor,
        body.numero, body.dataEmissao, body.dataVencimento, body.descricao,
    )
    return _fmt(dict(row))


@router.patch("/{cert_id}")
async def update_certidao(cert_id: int, body: CertidaoUpdate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    col_map = [
        ("nome","nome"), ("tipo","tipo"), ("orgaoEmissor","orgao_emissor"),
        ("numero","numero"), ("dataEmissao","data_emissao"),
        ("dataVencimento","data_vencimento"), ("descricao","descricao"),
    ]
    fields, values, idx = [], [], 1
    for attr, col in col_map:
        val = getattr(body, attr)
        if val is not None:
            fields.append(f"{col}=${idx}"); values.append(val); idx += 1
    if not fields:
        row = await pool.fetchrow("SELECT * FROM certidoes WHERE id=$1 AND user_id=$2", cert_id, current_user["id"])
        return _fmt(dict(row))
    values.extend([cert_id, current_user["id"]])
    row = await pool.fetchrow(
        f"UPDATE certidoes SET {', '.join(fields)} WHERE id=${idx} AND user_id=${idx+1} RETURNING *",
        *values,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Não encontrado")
    return _fmt(dict(row))


@router.delete("/{cert_id}", status_code=204)
async def delete_certidao(cert_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    r = await pool.execute(
        "DELETE FROM certidoes WHERE id=$1 AND user_id=$2", cert_id, current_user["id"]
    )
    if r == "DELETE 0":
        raise HTTPException(status_code=404, detail="Não encontrado")
