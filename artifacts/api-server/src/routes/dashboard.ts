import { Router } from "express";
import { db, favoritosTable, monitoramentosTable, alertasTable, oportunidadesTable } from "@workspace/db";
import { eq, count, sql, and } from "drizzle-orm";
import { requireAuth } from "../middlewares/auth";
import { searchLicitacoes } from "../lib/pncp";

const router = Router();

router.get("/dashboard", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;

  const [
    favCount,
    monCount,
    alertaCount,
    opCount,
    alertasRecentes,
    opRows,
    licitacoesResult,
  ] = await Promise.all([
    db.select({ c: count() }).from(favoritosTable).where(eq(favoritosTable.userId, userId)),
    db.select({ c: count() }).from(monitoramentosTable).where(eq(monitoramentosTable.userId, userId)),
    db.select({ c: count() }).from(alertasTable).where(and(eq(alertasTable.userId, userId), eq(alertasTable.lido, false))),
    db.select({ c: count() }).from(oportunidadesTable).where(eq(oportunidadesTable.userId, userId)),
    db.select().from(alertasTable).where(eq(alertasTable.userId, userId)).orderBy(sql`${alertasTable.criadoEm} desc`).limit(5),
    db.select().from(oportunidadesTable).where(eq(oportunidadesTable.userId, userId)),
    searchLicitacoes({ pagina: 1, tamanhoPagina: 5 }),
  ]);

  // Pipeline stats
  const estagios = ["identificada", "qualificada", "proposta", "disputa", "ganhou", "perdeu"];
  const oportunidadesPorEstagio = estagios.map((e) => {
    const rows = opRows.filter((o) => o.estagio === e);
    const valorTotal = rows.reduce((s, o) => s + parseFloat(o.valorEstimado ?? "0"), 0);
    return { estagio: e, total: rows.length, valorTotal };
  });
  const valorTotalPipeline = opRows
    .filter((o) => !["ganhou", "perdeu"].includes(o.estagio))
    .reduce((s, o) => s + parseFloat(o.valorEstimado ?? "0"), 0);

  // Modalidade stats from mock data
  const modalidades = new Map<string, number>();
  for (const l of licitacoesResult.data) {
    modalidades.set(l.modalidade, (modalidades.get(l.modalidade) ?? 0) + 1);
  }
  const licitacoesPorModalidade = Array.from(modalidades.entries()).map(([modalidade, total]) => ({
    modalidade,
    total,
  }));

  res.json({
    totalFavoritos: favCount[0]?.c ?? 0,
    totalMonitoramentos: monCount[0]?.c ?? 0,
    totalAlertasNaoLidos: alertaCount[0]?.c ?? 0,
    totalOportunidades: opCount[0]?.c ?? 0,
    valorTotalPipeline,
    licitacoesRecentes: licitacoesResult.data.map((l) => ({ ...l, isFavoritada: false })),
    alertasRecentes: alertasRecentes.map((a) => ({
      ...a,
      criadoEm: a.criadoEm.toISOString(),
    })),
    oportunidadesPorEstagio,
    licitacoesPorModalidade,
  });
});

export default router;
