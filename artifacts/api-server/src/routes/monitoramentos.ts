import { Router } from "express";
import { db, monitoramentosTable } from "@workspace/db";
import { and, eq } from "drizzle-orm";
import { requireAuth } from "../middlewares/auth";

const router = Router();

function parseRow(row: typeof monitoramentosTable.$inferSelect) {
  return {
    id: row.id,
    nome: row.nome,
    ativo: row.ativo,
    palavrasChave: JSON.parse(row.palavrasChave) as string[],
    modalidades: JSON.parse(row.modalidades) as string[],
    ufs: JSON.parse(row.ufs) as string[],
    esferas: JSON.parse(row.esferas) as string[],
    valorMin: row.valorMin ? parseFloat(row.valorMin) : null,
    valorMax: row.valorMax ? parseFloat(row.valorMax) : null,
    totalAlertas: row.totalAlertas,
    ultimaExecucao: row.ultimaExecucao?.toISOString() ?? null,
    criadoEm: row.criadoEm.toISOString(),
  };
}

router.get("/monitoramentos", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const rows = await db.select().from(monitoramentosTable).where(eq(monitoramentosTable.userId, userId));
  res.json(rows.map(parseRow));
});

router.post("/monitoramentos", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const { nome, palavrasChave, modalidades, ufs, esferas, valorMin, valorMax } = req.body as {
    nome: string;
    palavrasChave?: string[];
    modalidades?: string[];
    ufs?: string[];
    esferas?: string[];
    valorMin?: number;
    valorMax?: number;
  };

  if (!nome) {
    res.status(400).json({ error: "Nome obrigatório" });
    return;
  }

  const [created] = await db
    .insert(monitoramentosTable)
    .values({
      userId,
      nome,
      palavrasChave: JSON.stringify(palavrasChave ?? []),
      modalidades: JSON.stringify(modalidades ?? []),
      ufs: JSON.stringify(ufs ?? []),
      esferas: JSON.stringify(esferas ?? []),
      valorMin: valorMin?.toString() ?? null,
      valorMax: valorMax?.toString() ?? null,
    })
    .returning();

  res.status(201).json(parseRow(created!));
});

router.get("/monitoramentos/:id", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw!, 10);

  const rows = await db.select().from(monitoramentosTable).where(and(eq(monitoramentosTable.id, id), eq(monitoramentosTable.userId, userId))).limit(1);
  if (!rows[0]) {
    res.status(404).json({ error: "Monitoramento não encontrado" });
    return;
  }
  res.json(parseRow(rows[0]));
});

router.put("/monitoramentos/:id", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw!, 10);
  const body = req.body as {
    nome?: string;
    palavrasChave?: string[];
    modalidades?: string[];
    ufs?: string[];
    esferas?: string[];
    valorMin?: number;
    valorMax?: number;
    ativo?: boolean;
  };

  const updateData: Partial<typeof monitoramentosTable.$inferInsert> & { atualizadoEm: Date } = {
    atualizadoEm: new Date(),
  };
  if (body.nome !== undefined) updateData.nome = body.nome;
  if (body.palavrasChave !== undefined) updateData.palavrasChave = JSON.stringify(body.palavrasChave);
  if (body.modalidades !== undefined) updateData.modalidades = JSON.stringify(body.modalidades);
  if (body.ufs !== undefined) updateData.ufs = JSON.stringify(body.ufs);
  if (body.esferas !== undefined) updateData.esferas = JSON.stringify(body.esferas);
  if (body.valorMin !== undefined) updateData.valorMin = body.valorMin?.toString() ?? null;
  if (body.valorMax !== undefined) updateData.valorMax = body.valorMax?.toString() ?? null;
  if (body.ativo !== undefined) updateData.ativo = body.ativo;

  const [updated] = await db.update(monitoramentosTable).set(updateData).where(and(eq(monitoramentosTable.id, id), eq(monitoramentosTable.userId, userId))).returning();
  if (!updated) {
    res.status(404).json({ error: "Monitoramento não encontrado" });
    return;
  }
  res.json(parseRow(updated));
});

router.delete("/monitoramentos/:id", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw!, 10);
  await db.delete(monitoramentosTable).where(and(eq(monitoramentosTable.id, id), eq(monitoramentosTable.userId, userId)));
  res.json({ message: "Monitoramento excluído com sucesso" });
});

router.post("/monitoramentos/:id/toggle", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw!, 10);

  const rows = await db.select().from(monitoramentosTable).where(and(eq(monitoramentosTable.id, id), eq(monitoramentosTable.userId, userId))).limit(1);
  if (!rows[0]) {
    res.status(404).json({ error: "Não encontrado" });
    return;
  }

  const [updated] = await db.update(monitoramentosTable)
    .set({ ativo: !rows[0].ativo, atualizadoEm: new Date() })
    .where(and(eq(monitoramentosTable.id, id), eq(monitoramentosTable.userId, userId)))
    .returning();
  res.json(parseRow(updated!));
});

export default router;
