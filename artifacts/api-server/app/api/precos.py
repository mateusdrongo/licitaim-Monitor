"""
precos.py — Consulta de preços estimados e homologados.

Fonte primária: licitacoes_cache (banco local, alimentado pelo collector a cada ~20 min).
Sem dependência de APIs externas — os dados estão sempre disponíveis.

Tipos de consulta:
  estimado   — valor_estimado de todas as licitações que batem com o termo
  homologado — valor_estimado de licitações encerradas (adjudicadas/homologadas)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..core.deps import get_current_user
from ..db.session import get_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/precos", tags=["precos"])

_UFS_VALIDAS = {
    "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
    "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO",
}


@router.get("/historico")
async def historico_precos(
    q: str = Query(..., min_length=2, description="Descrição ou código do item"),
    uf: Optional[str] = Query(None),
    tipo: str = Query("estimado", pattern="^(estimado|homologado)$"),
    dataInicio: Optional[str] = Query(None),
    dataFim: Optional[str] = Query(None),
    pagina: int = Query(1, ge=1),
    current_user: dict = Depends(get_current_user),
):
    """
    Retorna preços de licitações que mencionam o item pesquisado.

    tipo=estimado   → todas as licitações (valor de referência pré-licitação)
    tipo=homologado → apenas encerradas (valor adjudicado/homologado)
    """
    pool = await get_pool()

    limit = 200      # máximo por consulta
    offset = (pagina - 1) * limit

    conditions: list[str] = [
        "valor_estimado IS NOT NULL",
        "valor_estimado > 0",
        "objeto ILIKE $1",
    ]
    args: list = [f"%{q}%"]
    idx = 2

    if tipo == "homologado":
        conditions.append(f"situacao = ANY(${idx}::text[])")
        args.append(["encerrada", "cancelada"])
        idx += 1

    if uf and uf.upper() in _UFS_VALIDAS:
        conditions.append(f"uf = ${idx}")
        args.append(uf.upper())
        idx += 1

    if dataInicio:
        conditions.append(f"data_publicacao >= ${idx}::timestamptz")
        args.append(dataInicio)
        idx += 1

    if dataFim:
        conditions.append(
            f"data_publicacao < ${idx}::timestamptz + interval '1 day'"
        )
        args.append(dataFim)
        idx += 1

    where = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            numero,
            objeto,
            orgao_nome,
            uf,
            municipio,
            modalidade,
            situacao,
            valor_estimado,
            data_publicacao,
            data_abertura,
            data_encerramento
        FROM licitacoes_cache
        {where}
        ORDER BY data_publicacao DESC NULLS LAST
        LIMIT {limit} OFFSET {offset}
    """

    count_sql = f"SELECT COUNT(*) FROM licitacoes_cache {where}"

    try:
        rows = await pool.fetch(sql, *args)
        total_count = await pool.fetchval(count_sql, *args)
    except Exception as exc:
        logger.error("historico_precos: erro ao consultar banco: %s", exc)
        return _empty_response(q)

    if not rows:
        return _empty_response(q)

    registros = []
    for r in rows:
        dt = r["data_publicacao"] or r["data_abertura"] or r["data_encerramento"]
        registros.append({
            "data":       dt.date().isoformat() if dt else None,
            "preco":      float(r["valor_estimado"]),
            "orgao":      r["orgao_nome"] or "",
            "uf":         r["uf"] or "",
            "municipio":  r["municipio"] or "",
            "licitacaoId": r["numero"] or "",
            "objeto":     (r["objeto"] or "")[:200],
            "modalidade": r["modalidade"] or "",
            "situacao":   r["situacao"] or "",
        })

    precos = [r["preco"] for r in registros]
    preco_medio  = sum(precos) / len(precos)
    preco_minimo = min(precos)
    preco_maximo = max(precos)

    return {
        "item":          q,
        "tipo":          tipo,
        "totalRegistros": int(total_count or len(registros)),
        "precoMedio":    round(preco_medio, 2),
        "precoMinimo":   round(preco_minimo, 2),
        "precoMaximo":   round(preco_maximo, 2),
        "registros":     registros,
        "pagina":        pagina,
        "totalPaginas":  max(1, -(-int(total_count or len(registros)) // limit)),
        "fonte":         "licitacoes_cache",
    }


def _empty_response(q: str) -> dict:
    return {
        "item":          q,
        "tipo":          "estimado",
        "totalRegistros": 0,
        "precoMedio":    0.0,
        "precoMinimo":   0.0,
        "precoMaximo":   0.0,
        "registros":     [],
        "pagina":        1,
        "totalPaginas":  1,
        "fonte":         "licitacoes_cache",
    }
