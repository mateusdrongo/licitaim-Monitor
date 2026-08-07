import { Router } from "express";
import { db, documentosTable } from "@workspace/db";
import { and, count, desc, eq } from "drizzle-orm";
import { requireAuth } from "../middlewares/auth";

const router = Router();

function parseRow(row: typeof documentosTable.$inferSelect) {
  return {
    id: row.id,
    nome: row.nome,
    categoria: row.categoria,
    licitacaoId: row.licitacaoId ?? null,
    licitacaoObjeto: row.licitacaoObjeto ?? null,
    url: row.url ?? null,
    tamanho: row.tamanho ?? null,
    tipo: row.tipo ?? null,
    descricao: row.descricao ?? null,
    criadoEm: row.criadoEm.toISOString(),
  };
}

router.get("/documentos", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const page = parseInt(String(req.query.page ?? "1"), 10);
  const limit = parseInt(String(req.query.limit ?? "20"), 10);
  const offset = (page - 1) * limit;

  const conditions = [eq(documentosTable.userId, userId)];
  if (req.query.licitacaoId) conditions.push(eq(documentosTable.licitacaoId, String(req.query.licitacaoId)));
  if (req.query.categoria) conditions.push(eq(documentosTable.categoria, String(req.query.categoria)));
  const where = and(...conditions);

  const [rows, totalRows] = await Promise.all([
    db.select().from(documentosTable).where(where).orderBy(desc(documentosTable.criadoEm)).limit(limit).offset(offset),
    db.select({ c: count() }).from(documentosTable).where(where),
  ]);

  const total = totalRows[0]?.c ?? 0;
  res.json({ data: rows.map(parseRow), total, page, totalPages: Math.ceil(total / limit) });
});

router.post("/documentos", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const { nome, categoria, licitacaoId, url, descricao } = req.body as {
    nome: string;
    categoria?: string;
    licitacaoId?: string;
    url?: string;
    descricao?: string;
  };

  if (!nome) {
    res.status(400).json({ error: "Nome obrigatório" });
    return;
  }

  const [created] = await db.insert(documentosTable).values({
    userId,
    nome,
    categoria: categoria ?? "outro",
    licitacaoId: licitacaoId ?? null,
    url: url ?? null,
    descricao: descricao ?? null,
  }).returning();

  res.status(201).json(parseRow(created!));
});

router.get("/documentos/:id", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw!, 10);
  const rows = await db.select().from(documentosTable).where(and(eq(documentosTable.id, id), eq(documentosTable.userId, userId))).limit(1);
  if (!rows[0]) {
    res.status(404).json({ error: "Documento não encontrado" });
    return;
  }
  res.json(parseRow(rows[0]));
});

router.patch("/documentos/:id", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw!, 10);
  const { nome, categoria, descricao, url } = req.body as {
    nome?: string;
    categoria?: string;
    descricao?: string;
    url?: string;
  };

  const updateData: Partial<typeof documentosTable.$inferInsert> & { atualizadoEm: Date } = { atualizadoEm: new Date() };
  if (nome !== undefined) updateData.nome = nome;
  if (categoria !== undefined) updateData.categoria = categoria;
  if (descricao !== undefined) updateData.descricao = descricao;
  if (url !== undefined) updateData.url = url;

  const [updated] = await db.update(documentosTable).set(updateData).where(and(eq(documentosTable.id, id), eq(documentosTable.userId, userId))).returning();
  if (!updated) {
    res.status(404).json({ error: "Documento não encontrado" });
    return;
  }
  res.json(parseRow(updated));
});

router.delete("/documentos/:id", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw!, 10);
  await db.delete(documentosTable).where(and(eq(documentosTable.id, id), eq(documentosTable.userId, userId)));
  res.json({ message: "Documento excluído com sucesso" });
});

export default router;
