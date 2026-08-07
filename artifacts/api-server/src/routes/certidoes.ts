import { Router } from "express";
import { db, certidoesTable } from "@workspace/db";
import { and, asc, eq } from "drizzle-orm";
import { requireAuth } from "../middlewares/auth";

const router = Router();

function computeStatus(dataVencimento: string | null): "ativa" | "vencida" | "a_vencer" | "sem_vencimento" {
  if (!dataVencimento) return "sem_vencimento";
  const venc = new Date(dataVencimento);
  const hoje = new Date();
  const diff = Math.ceil((venc.getTime() - hoje.getTime()) / (1000 * 60 * 60 * 24));
  if (diff < 0) return "vencida";
  if (diff <= 30) return "a_vencer";
  return "ativa";
}

function parseRow(row: typeof certidoesTable.$inferSelect) {
  return {
    id: row.id,
    nome: row.nome,
    tipo: row.tipo,
    orgaoEmissor: row.orgaoEmissor ?? null,
    numero: row.numero ?? null,
    dataEmissao: row.dataEmissao ?? null,
    dataVencimento: row.dataVencimento ?? null,
    status: computeStatus(row.dataVencimento),
    descricao: row.descricao ?? null,
    criadoEm: row.criadoEm.toISOString(),
  };
}

router.get("/certidoes", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const rows = await db
    .select()
    .from(certidoesTable)
    .where(eq(certidoesTable.userId, userId))
    .orderBy(asc(certidoesTable.dataVencimento));
  res.json(rows.map(parseRow));
});

router.post("/certidoes", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const { nome, tipo, orgaoEmissor, numero, dataEmissao, dataVencimento, descricao } = req.body as {
    nome: string;
    tipo?: string;
    orgaoEmissor?: string;
    numero?: string;
    dataEmissao?: string;
    dataVencimento?: string;
    descricao?: string;
  };

  if (!nome) {
    res.status(400).json({ error: "Nome obrigatório" });
    return;
  }

  const [created] = await db.insert(certidoesTable).values({
    userId,
    nome,
    tipo: tipo ?? "outro",
    orgaoEmissor: orgaoEmissor ?? null,
    numero: numero ?? null,
    dataEmissao: dataEmissao ?? null,
    dataVencimento: dataVencimento ?? null,
    descricao: descricao ?? null,
  }).returning();

  res.status(201).json(parseRow(created!));
});

router.patch("/certidoes/:id", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw!, 10);

  const { nome, tipo, orgaoEmissor, numero, dataEmissao, dataVencimento, descricao } = req.body as {
    nome?: string;
    tipo?: string;
    orgaoEmissor?: string;
    numero?: string;
    dataEmissao?: string;
    dataVencimento?: string;
    descricao?: string;
  };

  const upd: Partial<typeof certidoesTable.$inferInsert> & { atualizadoEm: Date } = { atualizadoEm: new Date() };
  if (nome !== undefined) upd.nome = nome;
  if (tipo !== undefined) upd.tipo = tipo;
  if (orgaoEmissor !== undefined) upd.orgaoEmissor = orgaoEmissor;
  if (numero !== undefined) upd.numero = numero;
  if (dataEmissao !== undefined) upd.dataEmissao = dataEmissao;
  if (dataVencimento !== undefined) upd.dataVencimento = dataVencimento;
  if (descricao !== undefined) upd.descricao = descricao;

  const [updated] = await db.update(certidoesTable).set(upd)
    .where(and(eq(certidoesTable.id, id), eq(certidoesTable.userId, userId)))
    .returning();

  if (!updated) {
    res.status(404).json({ error: "Certidão não encontrada" });
    return;
  }
  res.json(parseRow(updated));
});

router.delete("/certidoes/:id", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw!, 10);
  await db.delete(certidoesTable).where(and(eq(certidoesTable.id, id), eq(certidoesTable.userId, userId)));
  res.json({ message: "Certidão removida com sucesso" });
});

export default router;
