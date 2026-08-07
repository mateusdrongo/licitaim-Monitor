import { Router } from "express";
import { db, oportunidadesTable, favoritosTable, monitoramentosTable, alertasTable, certidoesTable } from "@workspace/db";
import { eq, and } from "drizzle-orm";
import { requireAuth } from "../middlewares/auth";

const router = Router();

router.get("/analytics", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;

  const [ops, favs, mons, alertas, certidoes] = await Promise.all([
    db.select().from(oportunidadesTable).where(eq(oportunidadesTable.userId, userId)),
    db.select().from(favoritosTable).where(eq(favoritosTable.userId, userId)),
    db.select().from(monitoramentosTable).where(eq(monitoramentosTable.userId, userId)),
    db.select().from(alertasTable).where(eq(alertasTable.userId, userId)),
    db.select().from(certidoesTable).where(eq(certidoesTable.userId, userId)),
  ]);

  // Win rate
  const ganhou = ops.filter((o) => o.estagio === "ganhou").length;
  const perdeu = ops.filter((o) => o.estagio === "perdeu").length;
  const taxaVitoria = ganhou + perdeu > 0 ? Math.round((ganhou / (ganhou + perdeu)) * 100) : 0;

  // Valor ganho
  const valorGanho = ops
    .filter((o) => o.estagio === "ganhou")
    .reduce((s, o) => s + parseFloat(o.valorEstimado ?? "0"), 0);

  // Pipeline ativo (excluindo ganhou/perdeu)
  const opsAtivas = ops.filter((o) => !["ganhou", "perdeu"].includes(o.estagio));
  const valorPipelineAtivo = opsAtivas.reduce((s, o) => s + parseFloat(o.valorEstimado ?? "0"), 0);

  // Probabilidade média ponderada
  const valorPonderado = opsAtivas.reduce((s, o) => {
    const prob = (o.probabilidade ?? 50) / 100;
    return s + parseFloat(o.valorEstimado ?? "0") * prob;
  }, 0);

  // Estagios breakdown
  const estagios = ["identificada", "qualificada", "proposta", "disputa", "ganhou", "perdeu"];
  const pipelinePorEstagio = estagios.map((e) => {
    const filtered = ops.filter((o) => o.estagio === e);
    return {
      estagio: e,
      quantidade: filtered.length,
      valor: filtered.reduce((s, o) => s + parseFloat(o.valorEstimado ?? "0"), 0),
    };
  });

  // Certidões vencendo em 30 dias
  const hoje = new Date();
  const certidoesAlerta = certidoes
    .filter((c) => {
      if (!c.dataVencimento) return false;
      const diff = Math.ceil((new Date(c.dataVencimento).getTime() - hoje.getTime()) / (1000 * 60 * 60 * 24));
      return diff <= 30;
    })
    .map((c) => {
      const diff = Math.ceil((new Date(c.dataVencimento!).getTime() - hoje.getTime()) / (1000 * 60 * 60 * 24));
      return { id: c.id, nome: c.nome, dataVencimento: c.dataVencimento, diasRestantes: diff };
    })
    .sort((a, b) => a.diasRestantes - b.diasRestantes);

  // Alertas por tipo
  const alertasPorTipo = [
    "nova_licitacao",
    "prazo_vencendo",
    "situacao_alterada",
    "nova_disputa",
    "preco_referencia",
  ].map((tipo) => ({
    tipo,
    total: alertas.filter((a) => a.tipo === tipo).length,
    naoLidos: alertas.filter((a) => a.tipo === tipo && !a.lido).length,
  }));

  // Monitoramentos top (por alertas gerados)
  const monitoramentosTop = mons
    .sort((a, b) => (b.totalAlertas ?? 0) - (a.totalAlertas ?? 0))
    .slice(0, 5)
    .map((m) => ({ id: m.id, nome: m.nome, ativo: m.ativo, totalAlertas: m.totalAlertas ?? 0 }));

  res.json({
    taxaVitoria,
    ganhou,
    perdeu,
    valorGanho,
    valorPipelineAtivo,
    valorPonderado,
    totalOportunidades: ops.length,
    totalFavoritos: favs.length,
    totalMonitoramentos: mons.length,
    totalAlertas: alertas.length,
    alertasNaoLidos: alertas.filter((a) => !a.lido).length,
    pipelinePorEstagio,
    certidoesAlerta,
    alertasPorTipo,
    monitoramentosTop,
  });
});

export default router;
