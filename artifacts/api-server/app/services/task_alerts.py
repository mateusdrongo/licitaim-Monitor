"""
task_alerts.py — Job diário que cria alertas automáticos para tarefas de gerenciamento
                  de licitações com prazos próximos ou vencidos.

Janelas verificadas:
  • tarefa_vencida  — prazo <= hoje (vencida ou vence hoje)
  • tarefa_prazo_1d — prazo == hoje + 1 (amanhã)
  • tarefa_prazo_3d — prazo in [hoje+2 .. hoje+3]
  • tarefa_prazo_7d — prazo in [hoje+4 .. hoje+7]

Deduplicação: não cria alerta se já existe um do mesmo tipo para a mesma tarefa
nas últimas 24 horas (identifica a tarefa via campo `licitacao_id` com prefixo
"tarefa_{id}").
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

logger = logging.getLogger("licitaim.task_alerts")


# ── Janelas de prazo ──────────────────────────────────────────────────────────
# Tupla: (tipo, dias_min, dias_max)
# dias_min=None significa "qualquer valor <= dias_max" (cobre vencidas + hoje).

_WINDOWS: list[tuple] = [
    # vencida ou vence hoje (dias <= 0)
    ("tarefa_vencida",  None, 0),
    # vence amanhã (dias == 1)
    ("tarefa_prazo_1d",    1, 1),
    # vence em 2 ou 3 dias
    ("tarefa_prazo_3d",    2, 3),
    # vence em 4 a 7 dias
    ("tarefa_prazo_7d",    4, 7),
]


def _classify(dias: int):
    """Retorna a tupla (tipo, dias_min, dias_max) correspondente a `dias`,
    ou None se não se enquadra em nenhuma janela."""
    for w in _WINDOWS:
        tipo, d_min, d_max = w
        if d_min is None:
            if dias <= d_max:
                return w
        else:
            if d_min <= dias <= d_max:
                return w
    return None


def _build_texts(
    tipo: str,
    dias_restantes: int,
    titulo_tarefa: str,
    objeto: str,
    prazo: date,
) -> tuple[str, str]:
    """Retorna (titulo_alerta, descricao) para o tipo e janela dados."""
    prazo_fmt = prazo.strftime("%d/%m/%Y")

    if tipo == "tarefa_vencida":
        if dias_restantes == 0:
            titulo    = f"🚨 Tarefa vence HOJE: {titulo_tarefa[:80]}"
            descricao = (
                f'A tarefa "{titulo_tarefa}" da licitacao "{objeto[:80]}" '
                f"vence hoje ({prazo_fmt}). "
                f"Acesse o gerenciamento para concluila."
            )
        else:
            atraso = abs(dias_restantes)
            titulo    = f"🚨 Tarefa VENCIDA ha {atraso}d: {titulo_tarefa[:80]}"
            descricao = (
                f'A tarefa "{titulo_tarefa}" da licitacao "{objeto[:80]}" '
                f"esta vencida ha {atraso} dia(s) (prazo era {prazo_fmt}). "
                f"Acesse o gerenciamento para concluila ou atualizar o prazo."
            )
    elif tipo == "tarefa_prazo_1d":
        titulo    = f"⚠️ Tarefa vence amanha: {titulo_tarefa[:80]}"
        descricao = (
            f'A tarefa "{titulo_tarefa}" da licitacao "{objeto[:80]}" '
            f"vence amanha ({prazo_fmt}). "
            f"Acesse o gerenciamento para concluila a tempo."
        )
    elif tipo == "tarefa_prazo_3d":
        titulo    = f"⏰ Tarefa vence em {dias_restantes}d: {titulo_tarefa[:80]}"
        descricao = (
            f'A tarefa "{titulo_tarefa}" da licitacao "{objeto[:80]}" '
            f"vence em {dias_restantes} dias ({prazo_fmt}). "
            f"Acesse o gerenciamento para acompanhar."
        )
    else:  # tarefa_prazo_7d
        titulo    = f"📅 Tarefa vence em {dias_restantes}d: {titulo_tarefa[:80]}"
        descricao = (
            f'A tarefa "{titulo_tarefa}" da licitacao "{objeto[:80]}" '
            f"vence em {dias_restantes} dias ({prazo_fmt}). "
            f"Planeje com antecedencia."
        )

    return titulo, descricao


# ── Job principal ─────────────────────────────────────────────────────────────

async def check_task_deadlines() -> dict:
    """
    Varre gerenciamento_tarefas buscando tarefas não concluídas com prazo
    nos próximos 7 dias ou já vencidas. Cria alertas na tabela `alertas`
    evitando duplicação dentro de 24 horas.

    Retorna resumo: {tasks_checked, alerts_created, alerts_skipped}.
    """
    from ..db.session import get_pool

    pool = await get_pool()
    hoje = date.today()

    # Tarefas não concluídas com prazo dentro da janela de interesse:
    # vencidas (qualquer data passada) até 7 dias à frente.
    rows = await pool.fetch(
        """
        SELECT
            t.id              AS tarefa_id,
            t.gerenciamento_id,
            t.titulo          AS tarefa_titulo,
            t.prazo,
            g.user_id,
            g.licitacao_objeto,
            g.licitacao_numero
        FROM gerenciamento_tarefas t
        JOIN licitacoes_gerenciadas g ON g.id = t.gerenciamento_id
        WHERE t.concluida = false
          AND t.prazo IS NOT NULL
          AND t.prazo <= $1
        ORDER BY t.prazo ASC
        """,
        hoje + timedelta(days=7),
    )

    alerts_created = 0
    alerts_skipped = 0
    tasks_checked  = len(rows)

    for row in rows:
        tarefa_id     = row["tarefa_id"]
        ger_id        = row["gerenciamento_id"]
        user_id       = str(row["user_id"])
        titulo_tarefa = row["tarefa_titulo"] or "Tarefa sem titulo"
        prazo: date   = row["prazo"]
        objeto        = row["licitacao_objeto"] or row["licitacao_numero"] or "Licitacao"

        dias_restantes = (prazo - hoje).days  # 0 = hoje, <0 = vencida, >0 = futuro

        window = _classify(dias_restantes)
        if window is None:
            # Fora de todas as janelas (não deveria ocorrer com a query atual)
            continue

        tipo = window[0]

        # Referência única: "tarefa_{id}" em licitacao_id — usada só para dedup
        ref_key = f"tarefa_{tarefa_id}"

        try:
            # Deduplicação: não cria se já existe alerta do mesmo tipo p/ esta tarefa em 24h
            existing = await pool.fetchval(
                """
                SELECT id FROM alertas
                WHERE user_id      = $1
                  AND tipo         = $2
                  AND licitacao_id = $3
                  AND criado_em    > NOW() - INTERVAL '24 hours'
                LIMIT 1
                """,
                user_id, tipo, ref_key,
            )
            if existing:
                alerts_skipped += 1
                logger.debug(
                    "task_alerts: tarefa %d tipo=%s ja tem alerta recente — pulando.",
                    tarefa_id, tipo,
                )
                continue
        except Exception as exc:
            logger.warning(
                "task_alerts: erro na deduplicação para tarefa %d, prosseguindo sem dedup: %s",
                tarefa_id, exc,
            )

        titulo, descricao = _build_texts(tipo, dias_restantes, titulo_tarefa, objeto, prazo)
        link = f"/gerenciamento/{ger_id}"

        try:
            await pool.execute(
                """
                INSERT INTO alertas
                    (user_id, tipo, titulo, descricao, licitacao_id, link, lido)
                VALUES ($1, $2, $3, $4, $5, $6, false)
                """,
                user_id, tipo, titulo, descricao, ref_key, link,
            )
            alerts_created += 1
            logger.info(
                "task_alerts: alerta criado — user=%s tarefa=%d tipo=%s link=%s",
                user_id, tarefa_id, tipo, link,
            )
        except Exception as exc:
            logger.warning(
                "task_alerts: erro ao criar alerta para tarefa %d: %s", tarefa_id, exc
            )

    # Registra execução na tabela job_runs (usada pelo startup para detectar misfires)
    try:
        await pool.execute(
            "INSERT INTO job_runs (job_name) VALUES ($1)",
            "check_task_deadlines",
        )
    except Exception as exc:
        logger.warning("task_alerts: falha ao registrar job_run: %s", exc)

    logger.info(
        "task_alerts: %d tarefas verificadas | %d alertas criados | %d ignorados (dedup).",
        tasks_checked, alerts_created, alerts_skipped,
    )
    return {
        "tasks_checked":  tasks_checked,
        "alerts_created": alerts_created,
        "alerts_skipped": alerts_skipped,
    }
