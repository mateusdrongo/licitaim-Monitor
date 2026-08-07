from fastapi import APIRouter, Depends, HTTPException
from datetime import date, timedelta
from typing import Optional
from pydantic import BaseModel
from ..core.deps import get_current_user
from ..db.session import get_pool

router = APIRouter(prefix="/agenda", tags=["agenda"])


def _urgencia_dias(dias: int) -> str:
    if dias <= 3:
        return "critico"
    if dias <= 14:
        return "atencao"
    return "normal"


# ─── GET /agenda ──────────────────────────────────────────────────────────────
@router.get("")
async def get_agenda(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    uid = current_user["id"]
    hoje = date.today()
    limite = hoje + timedelta(days=60)

    eventos = []

    # ── Oportunidades com prazo ───────────────────────────────────────────────
    ops = await pool.fetch(
        """SELECT id, titulo, estagio, prazo FROM oportunidades
           WHERE user_id=$1 AND prazo IS NOT NULL
             AND estagio NOT IN ('ganhou','perdeu')""",
        uid,
    )
    for op in ops:
        try:
            prazo_date = date.fromisoformat(str(op["prazo"])[:10])
        except (ValueError, TypeError):
            continue
        if prazo_date < hoje - timedelta(days=7) or prazo_date > limite:
            continue
        dias = (prazo_date - hoje).days
        eventos.append({
            "id":       f"op-{op['id']}",
            "tipo":     "oportunidade",
            "titulo":   op["titulo"],
            "data":     prazo_date.isoformat(),
            "urgencia": _urgencia_dias(dias),
            "status":   "vencido" if dias < 0 else "ativo",
            "link":     "/oportunidades",
            "descricao": f"Estágio: {op['estagio']}",
        })

    # ── Certidões a vencer ───────────────────────────────────────────────────
    certs = await pool.fetch(
        """SELECT id, nome, tipo, data_vencimento FROM certidoes
           WHERE user_id=$1 AND data_vencimento IS NOT NULL
             AND data_vencimento >= $2 AND data_vencimento <= $3""",
        uid, hoje - timedelta(days=7), limite,
    )
    for cert in certs:
        dv = cert["data_vencimento"]
        dias = (dv - hoje).days
        eventos.append({
            "id":       f"cert-{cert['id']}",
            "tipo":     "certidao",
            "titulo":   cert["nome"],
            "data":     dv.isoformat(),
            "urgencia": _urgencia_dias(dias),
            "status":   "vencida" if dias < 0 else ("a_vencer" if dias <= 30 else "ativa"),
            "link":     "/certidoes",
            "descricao": cert["tipo"],
        })

    # ── Alertas de prazo não lidos ───────────────────────────────────────────
    alertas = await pool.fetch(
        """SELECT id, titulo, descricao, licitacao_id, criado_em FROM alertas
           WHERE user_id=$1 AND tipo='prazo_vencendo' AND lido=false
           ORDER BY criado_em DESC LIMIT 20""",
        uid,
    )
    for alerta in alertas:
        eventos.append({
            "id":       f"alerta-{alerta['id']}",
            "tipo":     "alerta",
            "titulo":   alerta["titulo"],
            "data":     alerta["criado_em"].date().isoformat(),
            "urgencia": "atencao",
            "status":   "pendente",
            "link":     "/alertas",
            "descricao": alerta["descricao"],
        })

    # ── Eventos personalizados ───────────────────────────────────────────────
    custom = await pool.fetch(
        """SELECT id, titulo, descricao, data, observacao
           FROM agenda_eventos
           WHERE user_id=$1
             AND data >= $2 AND data <= $3
           ORDER BY data""",
        uid, hoje - timedelta(days=7), limite,
    )
    for ev in custom:
        dias = (ev["data"] - hoje).days
        desc_parts = []
        if ev["descricao"]:
            desc_parts.append(ev["descricao"])
        if ev["observacao"]:
            desc_parts.append(f"Obs: {ev['observacao']}")
        eventos.append({
            "id":       f"ev-{ev['id']}",
            "tipo":     "evento",
            "titulo":   ev["titulo"],
            "data":     ev["data"].isoformat(),
            "urgencia": _urgencia_dias(dias) if dias >= 0 else "critico",
            "status":   "vencido" if dias < 0 else "ativo",
            "link":     "",
            "descricao": " · ".join(desc_parts) if desc_parts else None,
            "evento_id": ev["id"],
        })

    eventos.sort(key=lambda e: e["data"])

    prox_7 = [
        e for e in eventos
        if 0 <= (date.fromisoformat(e["data"][:10]) - hoje).days <= 7
    ]
    resumo = {
        "total":        len(eventos),
        "criticos":     sum(1 for e in eventos if e["urgencia"] == "critico"),
        "atencao":      sum(1 for e in eventos if e["urgencia"] == "atencao"),
        "proximos7dias": len(prox_7),
    }

    return {"eventos": eventos, "resumo": resumo}


# ─── POST /agenda/eventos ─────────────────────────────────────────────────────
class EventoCreate(BaseModel):
    titulo: str
    data: str          # ISO date YYYY-MM-DD
    descricao: Optional[str] = None
    observacao: Optional[str] = None


@router.post("/eventos", status_code=201)
async def create_evento(
    body: EventoCreate,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    try:
        data_date = date.fromisoformat(body.data)
    except ValueError:
        raise HTTPException(status_code=422, detail="Data inválida. Use o formato YYYY-MM-DD.")

    row = await pool.fetchrow(
        """INSERT INTO agenda_eventos (user_id, titulo, descricao, data, observacao)
           VALUES ($1, $2, $3, $4, $5)
           RETURNING id, titulo, descricao, data, observacao, criado_em""",
        current_user["id"], body.titulo.strip(), body.descricao, data_date, body.observacao,
    )
    return {
        "id":         row["id"],
        "titulo":     row["titulo"],
        "descricao":  row["descricao"],
        "data":       row["data"].isoformat(),
        "observacao": row["observacao"],
        "criadoEm":   row["criado_em"].isoformat(),
    }


# ─── DELETE /agenda/eventos/{id} ─────────────────────────────────────────────
@router.delete("/eventos/{evento_id}", status_code=204)
async def delete_evento(
    evento_id: int,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    result = await pool.execute(
        "DELETE FROM agenda_eventos WHERE id=$1 AND user_id=$2",
        evento_id, current_user["id"],
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
