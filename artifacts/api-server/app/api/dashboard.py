from fastapi import APIRouter, Depends
import httpx
from datetime import date, datetime, timedelta, timezone
from ..core.deps import get_current_user
from ..db.session import get_pool

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def _fetch_licitacoes_recentes_db(pool) -> list[dict]:
    """Busca as 5 licitações mais recentes do cache local."""
    try:
        rows = await pool.fetch(
            """
            SELECT numero, orgao_nome, objeto, valor_estimado,
                   data_publicacao, data_abertura, modalidade, uf
            FROM licitacoes_cache
            ORDER BY data_publicacao DESC NULLS LAST, atualizado_em DESC
            LIMIT 5
            """
        )
        result = []
        for r in rows:
            result.append({
                "id":            r["numero"],
                "numero":        r["numero"],
                "orgaoNome":     r["orgao_nome"] or "",
                "objeto":        r["objeto"] or "",
                "valorEstimado": float(r["valor_estimado"]) if r["valor_estimado"] else None,
                "dataAbertura":  r["data_abertura"].isoformat() if r["data_abertura"] else None,
                "modalidade":    r["modalidade"] or "",
                "uf":            r["uf"] or "",
            })
        return result
    except Exception:
        return []


@router.get("")
async def get_dashboard(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    uid  = current_user["id"]
    hoje = date.today()
    agora = datetime.now(timezone.utc)
    inicio_hoje = datetime(agora.year, agora.month, agora.day)  # naive — coluna criado_em é naive no PG

    # ── KPIs base ────────────────────────────────────────────────────────────
    total_favoritos = await pool.fetchval(
        "SELECT COUNT(*) FROM favoritos WHERE user_id=$1", uid
    )
    monitoramentos_ativos = await pool.fetchval(
        "SELECT COUNT(*) FROM monitoramentos WHERE user_id=$1 AND ativo=true", uid
    )
    alertas_nao_lidos = await pool.fetchval(
        "SELECT COUNT(*) FROM alertas WHERE user_id=$1 AND lido=false", uid
    )

    oportunidades = await pool.fetch(
        "SELECT estagio, valor_estimado, prazo, criado_em FROM oportunidades WHERE user_id=$1", uid
    )
    pipeline_valor = 0.0
    ops_vigentes   = 0
    ops_novas_hoje = 0
    ops_iminencia  = 0

    for op in oportunidades:
        ativo = op["estagio"] not in ("ganhou", "perdeu")
        if ativo:
            ops_vigentes += 1
            try:
                pipeline_valor += float(op["valor_estimado"]) if op["valor_estimado"] else 0
            except (ValueError, TypeError):
                pass
            # criado hoje
            if op.get("criado_em"):
                created = op["criado_em"]
                if hasattr(created, "date"):
                    if created.date() == hoje:
                        ops_novas_hoje += 1
                elif str(created)[:10] == str(hoje):
                    ops_novas_hoje += 1
            # iminência (prazo nos próximos 3 dias)
            if op.get("prazo"):
                try:
                    prazo_d = date.fromisoformat(str(op["prazo"])[:10])
                    if 0 <= (prazo_d - hoje).days <= 3:
                        ops_iminencia += 1
                except (ValueError, TypeError):
                    pass

    # ── Novos andamentos (alertas de hoje) ───────────────────────────────────
    novos_andamentos = await pool.fetchval(
        "SELECT COUNT(*) FROM alertas WHERE user_id=$1 AND criado_em >= $2",
        uid, inicio_hoje,
    )

    # ── Certidões vencendo em 30 dias ────────────────────────────────────────
    certidoes_vencendo = await pool.fetchval(
        """SELECT COUNT(*) FROM certidoes
           WHERE user_id=$1 AND data_vencimento IS NOT NULL
             AND data_vencimento BETWEEN $2 AND $3""",
        uid, hoje, hoje + timedelta(days=30),
    )

    # ── Documentos pendentes (sem URL) ───────────────────────────────────────
    docs_pendentes = await pool.fetchval(
        "SELECT COUNT(*) FROM documentos WHERE user_id=$1 AND (url IS NULL OR url='')",
        uid,
    )

    # ── Alertas recentes ─────────────────────────────────────────────────────
    alertas_recentes = await pool.fetch(
        """SELECT id, tipo, titulo, descricao, lido,
                  licitacao_id, licitacao_objeto,
                  monitoramento_nome, criado_em
           FROM alertas WHERE user_id=$1
           ORDER BY criado_em DESC LIMIT 5""",
        uid,
    )

    # ── Licitações recentes (do cache local) ────────────────────────────────
    licitacoes_recentes = await _fetch_licitacoes_recentes_db(pool)

    # ── Licitações por UF (dados reais do cache) ─────────────────────────────
    import json
    mon_ufs_rows = await pool.fetch(
        "SELECT ufs FROM monitoramentos WHERE user_id=$1 AND ativo=true", uid
    )
    monitored_ufs = set()
    for row in mon_ufs_rows:
        try:
            uf_list = json.loads(row["ufs"]) if isinstance(row["ufs"], str) else (row["ufs"] or [])
            for uf in uf_list:
                monitored_ufs.add(uf.upper())
        except Exception:
            pass

    uf_rows = await pool.fetch(
        """SELECT uf, COUNT(*) AS total
           FROM licitacoes_cache
           WHERE uf IS NOT NULL AND uf <> ''
           GROUP BY uf
           ORDER BY total DESC
           LIMIT 8"""
    )
    max_uf = int(uf_rows[0]["total"]) if uf_rows else 1
    licitacoes_por_uf = [
        {
            "uf":         row["uf"],
            "total":      int(row["total"]),
            "percentual": round(int(row["total"]) / max_uf * 100),
            "monitorado": row["uf"] in monitored_ufs,
        }
        for row in uf_rows
    ]

    return {
        # ── KPIs principais ──
        "valorTotalPipeline":    pipeline_valor,
        "totalOportunidades":    ops_vigentes,
        "totalAlertasNaoLidos":  int(alertas_nao_lidos or 0),
        "totalMonitoramentos":   int(monitoramentos_ativos or 0),
        "totalFavoritos":        int(total_favoritos or 0),

        # ── Novidades / Oportunidades ──
        "novasOportunidadesHoje":  ops_novas_hoje,
        "oportunidadesVigentes":   ops_vigentes,
        "iminenciaEncerramento":   ops_iminencia,
        "novosAndamentos":         int(novos_andamentos or 0),

        # ── Gestão ──
        "tarefasHoje":       0,       # sem tabela de tarefas por enquanto
        "tarefasAtrasadas":  0,
        "certidoesVencendo": int(certidoes_vencendo or 0),
        "documentosPendentes": int(docs_pendentes or 0),

        # ── Mapa / Ranking ──
        "licitacoesPorUf": licitacoes_por_uf,

        # ── Listas ──
        "licitacoesRecentes": licitacoes_recentes,
        "alertasRecentes": [
            {
                "id":               a["id"],
                "tipo":             a["tipo"],
                "titulo":           a["titulo"],
                "descricao":        a["descricao"],
                "lido":             a["lido"],
                "licitacaoId":      a["licitacao_id"],
                "licitacaoObjeto":  a["licitacao_objeto"],
                "monitoramentoNome": a["monitoramento_nome"],
                "criadoEm":         a["criado_em"].isoformat() if a["criado_em"] else None,
            }
            for a in alertas_recentes
        ],
    }
