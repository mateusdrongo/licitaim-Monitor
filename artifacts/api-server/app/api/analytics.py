from fastapi import APIRouter, Depends
from datetime import date, timedelta
from ..core.deps import get_current_user
from ..db.session import get_pool

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("")
async def get_analytics(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    uid = current_user["id"]
    hoje = date.today()

    # ── Oportunidades ────────────────────────────────────────────────────────
    ops = await pool.fetch(
        "SELECT estagio, valor_estimado, probabilidade FROM oportunidades WHERE user_id=$1", uid
    )

    def to_num(val):
        try:
            return float(val) if val else 0.0
        except (ValueError, TypeError):
            return 0.0

    ganhou_list = [o for o in ops if o["estagio"] == "ganhou"]
    perdeu_list  = [o for o in ops if o["estagio"] == "perdeu"]
    total_final  = len(ganhou_list) + len(perdeu_list)
    taxa_vitoria = round(len(ganhou_list) / total_final * 100) if total_final > 0 else 0
    valor_ganho  = sum(to_num(o["valor_estimado"]) for o in ganhou_list)
    ativas       = [o for o in ops if o["estagio"] not in ("ganhou", "perdeu")]
    valor_pipeline  = sum(to_num(o["valor_estimado"]) for o in ativas)
    valor_ponderado = sum(
        to_num(o["valor_estimado"]) * (o["probabilidade"] or 0) / 100 for o in ativas
    )

    # ── Pipeline por estágio ─────────────────────────────────────────────────
    ESTAGIOS = ["identificada", "qualificada", "proposta", "disputa", "ganhou", "perdeu"]
    pipeline_por_estagio = []
    for est in ESTAGIOS:
        items = [o for o in ops if o["estagio"] == est]
        pipeline_por_estagio.append({
            "estagio":    est,
            "quantidade": len(items),
            "valor":      sum(to_num(o["valor_estimado"]) for o in items),
        })

    # ── Alertas por tipo (com naoLidos) ──────────────────────────────────────
    alertas_rows = await pool.fetch(
        """SELECT tipo,
                  COUNT(*) AS total,
                  SUM(CASE WHEN lido = false THEN 1 ELSE 0 END) AS nao_lidos
           FROM alertas WHERE user_id=$1
           GROUP BY tipo""",
        uid,
    )
    alertas_por_tipo = [
        {"tipo": r["tipo"], "total": int(r["total"]), "naoLidos": int(r["nao_lidos"])}
        for r in alertas_rows
    ]

    # ── Certidões vencendo (≤30 dias, inclusive vencidas) ───────────────────
    certs_alerta_rows = await pool.fetch(
        """SELECT id, nome, data_vencimento
           FROM certidoes
           WHERE user_id=$1
             AND data_vencimento IS NOT NULL
             AND data_vencimento <= $2
           ORDER BY data_vencimento ASC
           LIMIT 5""",
        uid,
        hoje + timedelta(days=30),
    )
    certidoes_alerta = [
        {
            "id":             r["id"],
            "nome":           r["nome"],
            "dataVencimento": r["data_vencimento"].isoformat() if r["data_vencimento"] else None,
            "diasRestantes":  (r["data_vencimento"] - hoje).days if r["data_vencimento"] else 0,
        }
        for r in certs_alerta_rows
    ]

    # ── Monitoramentos mais ativos ───────────────────────────────────────────
    top_mon_rows = await pool.fetch(
        """SELECT id, nome, ativo, total_alertas
           FROM monitoramentos
           WHERE user_id=$1
           ORDER BY total_alertas DESC NULLS LAST
           LIMIT 5""",
        uid,
    )
    monitoramentos_top = [
        {
            "id":          r["id"],
            "nome":        r["nome"],
            "ativo":       bool(r["ativo"]),
            "totalAlertas": int(r["total_alertas"] or 0),
        }
        for r in top_mon_rows
    ]

    return {
        "taxaVitoria":      taxa_vitoria,
        "ganhou":           len(ganhou_list),
        "perdeu":           len(perdeu_list),
        "valorGanho":       valor_ganho,
        "valorPipelineAtivo": valor_pipeline,
        "valorPonderado":   valor_ponderado,
        "totalOportunidades": len(ops),
        "pipelinePorEstagio": pipeline_por_estagio,
        "alertasPorTipo":   alertas_por_tipo,
        "certidoesAlerta":  certidoes_alerta,
        "monitoramentosTop": monitoramentos_top,
    }
