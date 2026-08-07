from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..core.deps import get_current_user
from ..db.session import get_pool

router = APIRouter(prefix="/favoritos", tags=["favoritos"])


class FavoritoCreate(BaseModel):
    licitacaoId: str
    nota: Optional[str] = None
    licitacaoObjeto: Optional[str] = None
    licitacaoOrgao: Optional[str] = None
    licitacaoUf: Optional[str] = None
    licitacaoModalidade: Optional[str] = None
    licitacaoSituacao: Optional[str] = None
    licitacaoValor: Optional[str] = None


def _row_to_fav(r: dict) -> dict:
    """
    Converte row do banco em objeto com campo 'licitacao' aninhado,
    conforme esperado pela página Favoritos.tsx.
    """
    valor_raw = r.get("licitacao_valor")
    try:
        valor_float: Optional[float] = float(valor_raw) if valor_raw else None
    except (ValueError, TypeError):
        valor_float = None

    return {
        "id":          r["id"],
        "licitacaoId": r["licitacao_id"],
        "nota":        r.get("nota"),
        "criadoEm":    r["criado_em"].isoformat() if r.get("criado_em") else None,
        "licitacao": {
            "numero":       r.get("licitacao_id", ""),        # controle / número
            "objeto":       r.get("licitacao_objeto") or "",
            "orgaoNome":    r.get("licitacao_orgao") or "",
            "uf":           r.get("licitacao_uf") or "",
            "modalidade":   r.get("licitacao_modalidade") or "",
            "situacao":     r.get("licitacao_situacao") or "",
            "valorEstimado": valor_float,
        },
    }


@router.get("")
async def list_favoritos(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT id, licitacao_id, nota, licitacao_objeto, licitacao_orgao,
                  licitacao_uf, licitacao_modalidade, licitacao_situacao,
                  licitacao_valor, criado_em
           FROM favoritos WHERE user_id=$1 ORDER BY criado_em DESC""",
        current_user["id"],
    )
    items = [_row_to_fav(dict(r)) for r in rows]
    return {"data": items, "total": len(items)}


@router.post("", status_code=201)
async def add_favorito(body: FavoritoCreate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    existing = await pool.fetchrow(
        "SELECT id FROM favoritos WHERE user_id=$1 AND licitacao_id=$2",
        current_user["id"], body.licitacaoId,
    )
    if existing:
        raise HTTPException(status_code=409, detail="Já favoritado")

    row = await pool.fetchrow(
        """INSERT INTO favoritos
           (user_id, licitacao_id, nota, licitacao_objeto, licitacao_orgao,
            licitacao_uf, licitacao_modalidade, licitacao_situacao, licitacao_valor)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
           RETURNING id, licitacao_id, nota, licitacao_objeto, licitacao_orgao,
                     licitacao_uf, licitacao_modalidade, licitacao_situacao,
                     licitacao_valor, criado_em""",
        current_user["id"], body.licitacaoId, body.nota, body.licitacaoObjeto,
        body.licitacaoOrgao, body.licitacaoUf, body.licitacaoModalidade,
        body.licitacaoSituacao, body.licitacaoValor,
    )
    return _row_to_fav(dict(row))


@router.delete("/by-licitacao/{licitacao_id:path}", status_code=204)
async def remove_favorito_by_licitacao(licitacao_id: str, current_user: dict = Depends(get_current_user)):
    """Remove favorito pelo licitacao_id (sem precisar do id interno)."""
    pool = await get_pool()
    result = await pool.execute(
        "DELETE FROM favoritos WHERE user_id=$1 AND licitacao_id=$2",
        current_user["id"], licitacao_id,
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Não encontrado")


@router.get("/check/{licitacao_id:path}", status_code=200)
async def check_favorito(licitacao_id: str, current_user: dict = Depends(get_current_user)):
    """Verifica se uma licitação está favoritada pelo usuário atual."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id FROM favoritos WHERE user_id=$1 AND licitacao_id=$2",
        current_user["id"], licitacao_id,
    )
    return {"isFavoritada": row is not None}


@router.delete("/{fav_id}", status_code=204)
async def remove_favorito(fav_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    result = await pool.execute(
        "DELETE FROM favoritos WHERE id=$1 AND user_id=$2", fav_id, current_user["id"]
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Não encontrado")
