import { Router } from "express";
import { db, alertasTable } from "@workspace/db";
import { and, count, desc, eq, sql } from "drizzle-orm";
import { requireAuth } from "../middlewares/auth";

const router = Router();

function parseRow(row: typeof alertasTable.$inferSelect) {
  return {
    id: row.id,
    tipo: row.tipo,
    titulo: row.titulo,
    descricao: row.descricao,
    lido: row.lido,
    licitacaoId: row.licitacaoId ?? null,
    licitacaoObjeto: row.licitacaoObjeto ?? null,
    monitoramentoNome: row.monitoramentoNome ?? null,
    criadoEm: row.criadoEm.toISOString(),
  };
}

router.get("/alertas", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const page = parseInt(String(req.query.page ?? "1"), 10);
  const limit = parseInt(String(req.query.limit ?? "30"), 10);
  const offset = (page - 1) * limit;
  const lido = req.query.lido !== undefined ? req.query.lido === "true" : undefined;
  const tipo = req.query.tipo ? String(req.query.tipo) : undefined;

  const conditions = [eq(alertasTable.userId, userId)];
  if (lido !== undefined) conditions.push(eq(alertasTable.lido, lido));
  if (tipo) conditions.push(eq(alertasTable.tipo, tipo));
  const where = and(...conditions);

  const [rows, totalRows, naoLidosRows] = await Promise.all([
    db.select().from(alertasTable).where(where).orderBy(desc(alertasTable.criadoEm)).limit(limit).offset(offset),
    db.select({ c: count() }).from(alertasTable).where(where),
    db.select({ c: count() }).from(alertasTable).where(and(eq(alertasTable.userId, userId), eq(alertasTable.lido, false))),
  ]);

  const total = totalRows[0]?.c ?? 0;
  res.json({
    data: rows.map(parseRow),
    total,
    page,
    totalPages: Math.ceil(total / limit),
    totalNaoLidos: naoLidosRows[0]?.c ?? 0,
  });
});

router.get("/alertas/nao-lidos", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const rows = await db.select({ c: count() }).from(alertasTable).where(and(eq(alertasTable.userId, userId), eq(alertasTable.lido, false)));
  res.json({ count: rows[0]?.c ?? 0 });
});

router.post("/alertas/:id/ler", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw!, 10);

  const [updated] = await db.update(alertasTable).set({ lido: true }).where(and(eq(alertasTable.id, id), eq(alertasTable.userId, userId))).returning();
  if (!updated) {
    res.status(404).json({ error: "Alerta não encontrado" });
    return;
  }
  res.json(parseRow(updated));
});

router.post("/alertas/ler-todos", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  await db.update(alertasTable).set({ lido: true }).where(and(eq(alertasTable.userId, userId), eq(alertasTable.lido, false)));
  res.json({ message: "Todos alertas marcados como lidos" });
});

export default router;
