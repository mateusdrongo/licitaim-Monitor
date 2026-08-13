"""
precos.py — Consulta de preços estimados e homologados.

Fonte primária: licitacoes_cache (banco local, alimentado pelo collector a cada ~20 min).
Sem dependência de APIs externas — os dados estão sempre disponíveis.

Tipos de consulta:
  estimado   — valor_estimado de todas as licitações que batem com o termo
  homologado — valor_estimado de licitações com situacao='encerrada' (processos concluídos)

Nota: o banco armazena apenas valor_estimado (referência pré-licitação). Não há campo de
valor adjudicado/homologado na fonte de dados atual; o modo "homologado" restringe os
resultados a processos encerrados, mas os valores exibidos continuam sendo estimativas.

Estatísticas (precoMedio, precoMinimo, precoMaximo) são calculadas sobre o conjunto
completo de resultados do filtro, não apenas sobre a página atual.
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


@router.get("/status")
async def precos_status(
    current_user: dict = Depends(get_current_user),
):
    """
    Retorna a contagem total de licitações na base local.
    Usado pelo frontend para detectar quando o banco ainda está vazio (collector não rodou).
    """
    pool = await get_pool()
    try:
        row = await pool.fetchrow(
            "SELECT COUNT(*) AS total FROM licitacoes_cache"
        )
        total = int(row["total"] or 0)
    except Exception as exc:
        logger.error("precos_status: erro ao consultar banco: %s", exc)
        total = 0

    return {"totalLicitacoes": total, "populado": total > 0}


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
    tipo=homologado → apenas licitações encerradas (situacao='encerrada')

    Nota: ambos os modos exibem valor_estimado. Licitações canceladas ou suspensas
    são excluídas do modo homologado pois não chegaram à adjudicação.

    Estatísticas calculadas sobre o conjunto completo de resultados (não apenas a página).
    """
    pool = await get_pool()

    limit = 200      # máximo por página
    offset = (pagina - 1) * limit

    conditions: list[str] = [
        "valor_estimado IS NOT NULL",
        "valor_estimado > 0",
        "objeto ILIKE $1",
    ]
    args: list = [f"%{q}%"]
    idx = 2

    # homologado: apenas processos efetivamente encerrados (não cancelados/suspensos)
    if tipo == "homologado":
        conditions.append(f"situacao = ${idx}")
        args.append("encerrada")
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

    # Page query
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

    # Full-dataset aggregate (count + stats) — no pagination, covers the entire filter
    agg_sql = f"""
        SELECT
            COUNT(*)                    AS total,
            AVG(valor_estimado)         AS media,
            MIN(valor_estimado)         AS minimo,
            MAX(valor_estimado)         AS maximo
        FROM licitacoes_cache
        {where}
    """

    try:
        rows = await pool.fetch(sql, *args)
        agg  = await pool.fetchrow(agg_sql, *args)
    except Exception as exc:
        logger.error("historico_precos: erro ao consultar banco: %s", exc)
        return _empty_response(q, tipo, pagina)

    total_count = int(agg["total"] or 0)

    if total_count == 0:
        return _empty_response(q, tipo, pagina)

    registros = []
    for r in rows:
        dt = r["data_publicacao"] or r["data_abertura"] or r["data_encerramento"]
        registros.append({
            "data":        dt.date().isoformat() if dt else None,
            "preco":       float(r["valor_estimado"]),
            "orgao":       r["orgao_nome"] or "",
            "uf":          r["uf"] or "",
            "municipio":   r["municipio"] or "",
            "licitacaoId": r["numero"] or "",
            "objeto":      (r["objeto"] or "")[:200],
            "modalidade":  r["modalidade"] or "",
            "situacao":    r["situacao"] or "",
        })

    # Stats come from the full-result aggregate, not the current page
    preco_medio  = float(agg["media"]  or 0)
    preco_minimo = float(agg["minimo"] or 0)
    preco_maximo = float(agg["maximo"] or 0)

    return {
        "item":           q,
        "tipo":           tipo,
        "totalRegistros": total_count,
        "precoMedio":     round(preco_medio, 2),
        "precoMinimo":    round(preco_minimo, 2),
        "precoMaximo":    round(preco_maximo, 2),
        "registros":      registros,
        "pagina":         pagina,
        "totalPaginas":   max(1, -(-total_count // limit)),
        "fonte":          "licitacoes_cache",
    }


def _empty_response(q: str, tipo: str = "estimado", pagina: int = 1) -> dict:
    return {
        "item":           q,
        "tipo":           tipo,
        "totalRegistros": 0,
        "precoMedio":     0.0,
        "precoMinimo":    0.0,
        "precoMaximo":    0.0,
        "registros":      [],
        "pagina":         pagina,
        "totalPaginas":   1,
        "fonte":          "licitacoes_cache",
    }
