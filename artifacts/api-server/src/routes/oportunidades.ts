import { Router } from "express";
import { db, oportunidadesTable } from "@workspace/db";
import { and, desc, eq } from "drizzle-orm";
import { requireAuth } from "../middlewares/auth";

const router = Router();

function parseRow(row: typeof oportunidadesTable.$inferSelect) {
  return {
    id: row.id,
    titulo: row.titulo,
    estagio: row.estagio,
    valorEstimado: row.valorEstimado ? parseFloat(row.valorEstimado) : null,
    probabilidade: row.probabilidade ?? null,
    licitacaoId: row.licitacaoId ?? null,
    licitacaoObjeto: row.licitacaoObjeto ?? null,
    responsavelNome: row.responsavelNome ?? null,
    responsavelId: row.responsavelId ?? null,
    prazo: row.prazo ?? null,
    notas: row.notas ?? null,
    tags: JSON.parse(row.tags) as string[],
    criadoEm: row.criadoEm.toISOString(),
    atualizadoEm: row.atualizadoEm.toISOString(),
  };
}

router.get("/oportunidades", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const conditions = [eq(oportunidadesTable.userId, userId)];
  if (req.query.estagio) conditions.push(eq(oportunidadesTable.estagio, String(req.query.estagio)));
  if (req.query.responsavelId) conditions.push(eq(oportunidadesTable.responsavelId, parseInt(String(req.query.responsavelId), 10)));

  const rows = await db.select().from(oportunidadesTable).where(and(...conditions)).orderBy(desc(oportunidadesTable.criadoEm));
  res.json(rows.map(parseRow));
});

router.post("/oportunidades", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const { titulo, estagio, valorEstimado, probabilidade, licitacaoId, responsavelId, prazo, notas, tags } = req.body as {
    titulo: string;
    estagio?: string;
    valorEstimado?: number;
    probabilidade?: number;
    licitacaoId?: string;
    responsavelId?: number;
    prazo?: string;
    notas?: string;
    tags?: string[];
  };

  if (!titulo) {
    res.status(400).json({ error: "Título obrigatório" });
    return;
  }

  const [created] = await db.insert(oportunidadesTable).values({
    userId,
    titulo,
    estagio: estagio ?? "identificada",
    valorEstimado: valorEstimado?.toString() ?? null,
    probabilidade: probabilidade ?? null,
    licitacaoId: licitacaoId ?? null,
    responsavelId: responsavelId ?? null,
    prazo: prazo ?? null,
    notas: notas ?? null,
    tags: JSON.stringify(tags ?? []),
  }).returning();

  res.status(201).json(parseRow(created!));
});

router.get("/oportunidades/pipeline-stats", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const rows = await db.select().from(oportunidadesTable).where(eq(oportunidadesTable.userId, userId));
  const estagios = ["identificada", "qualificada", "proposta", "disputa", "ganhou", "perdeu"];
  const stats = estagios.map((e) => {
    const filtered = rows.filter((r) => r.estagio === e);
    return {
      estagio: e,
      total: filtered.length,
      valorTotal: filtered.reduce((s, r) => s + parseFloat(r.valorEstimado ?? "0"), 0),
    };
  });
  res.json(stats);
});

router.get("/oportunidades/:id", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw!, 10);
  const rows = await db.select().from(oportunidadesTable).where(and(eq(oportunidadesTable.id, id), eq(oportunidadesTable.userId, userId))).limit(1);
  if (!rows[0]) {
    res.status(404).json({ error: "Oportunidade não encontrada" });
    return;
  }
  res.json(parseRow(rows[0]));
});

router.patch("/oportunidades/:id", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw!, 10);
  const { titulo, estagio, valorEstimado, probabilidade, responsavelId, prazo, notas, tags } = req.body as {
    titulo?: string;
    estagio?: string;
    valorEstimado?: number;
    probabilidade?: number;
    responsavelId?: number;
    prazo?: string;
    notas?: string;
    tags?: string[];
  };

  const updateData: Partial<typeof oportunidadesTable.$inferInsert> & { atualizadoEm: Date } = { atualizadoEm: new Date() };
  if (titulo !== undefined) updateData.titulo = titulo;
  if (estagio !== undefined) updateData.estagio = estagio;
  if (valorEstimado !== undefined) updateData.valorEstimado = valorEstimado?.toString() ?? null;
  if (probabilidade !== undefined) updateData.probabilidade = probabilidade;
  if (responsavelId !== undefined) updateData.responsavelId = responsavelId;
  if (prazo !== undefined) updateData.prazo = prazo;
  if (notas !== undefined) updateData.notas = notas;
  if (tags !== undefined) updateData.tags = JSON.stringify(tags);

  const [updated] = await db.update(oportunidadesTable).set(updateData).where(and(eq(oportunidadesTable.id, id), eq(oportunidadesTable.userId, userId))).returning();
  if (!updated) {
    res.status(404).json({ error: "Oportunidade não encontrada" });
    return;
  }
  res.json(parseRow(updated));
});

router.delete("/oportunidades/:id", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw!, 10);
  await db.delete(oportunidadesTable).where(and(eq(oportunidadesTable.id, id), eq(oportunidadesTable.userId, userId)));
  res.json({ message: "Oportunidade removida com sucesso" });
});

export default router;
