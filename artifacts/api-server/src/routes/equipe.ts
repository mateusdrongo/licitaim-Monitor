import { Router } from "express";
import { db, equipeMembrosTable } from "@workspace/db";
import { and, eq } from "drizzle-orm";
import { requireAuth } from "../middlewares/auth";

const router = Router();

function parseRow(row: typeof equipeMembrosTable.$inferSelect) {
  return {
    id: row.id,
    nome: row.nome,
    email: row.email,
    papel: row.papel,
    status: row.status,
    avatarUrl: row.avatarUrl ?? null,
    criadoEm: row.criadoEm.toISOString(),
  };
}

router.get("/equipe", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const rows = await db.select().from(equipeMembrosTable).where(eq(equipeMembrosTable.ownerId, userId));
  res.json(rows.map(parseRow));
});

router.post("/equipe", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const { email, papel } = req.body as { email: string; papel?: string };

  if (!email) {
    res.status(400).json({ error: "Email obrigatório" });
    return;
  }

  const nome = email.split("@")[0] ?? email;
  const [created] = await db.insert(equipeMembrosTable).values({
    ownerId: userId,
    nome,
    email,
    papel: papel ?? "visualizador",
    status: "pendente",
  }).returning();

  res.status(201).json(parseRow(created!));
});

router.patch("/equipe/:id", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw!, 10);
  const { papel, status } = req.body as { papel?: string; status?: string };

  const updateData: Partial<typeof equipeMembrosTable.$inferInsert> & { atualizadoEm: Date } = { atualizadoEm: new Date() };
  if (papel !== undefined) updateData.papel = papel;
  if (status !== undefined) updateData.status = status;

  const [updated] = await db.update(equipeMembrosTable).set(updateData).where(and(eq(equipeMembrosTable.id, id), eq(equipeMembrosTable.ownerId, userId))).returning();
  if (!updated) {
    res.status(404).json({ error: "Membro não encontrado" });
    return;
  }
  res.json(parseRow(updated));
});

router.delete("/equipe/:id", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw!, 10);
  await db.delete(equipeMembrosTable).where(and(eq(equipeMembrosTable.id, id), eq(equipeMembrosTable.ownerId, userId)));
  res.json({ message: "Membro removido com sucesso" });
});

export default router;
