import { Router } from "express";
import { db, favoritosTable } from "@workspace/db";
import { and, count, desc, eq } from "drizzle-orm";
import { requireAuth } from "../middlewares/auth";
import { searchLicitacoes } from "../lib/pncp";

const router = Router();

router.get("/favoritos", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const page = parseInt(String(req.query.page ?? "1"), 10);
  const limit = parseInt(String(req.query.limit ?? "20"), 10);
  const offset = (page - 1) * limit;

  const [rows, totalRows] = await Promise.all([
    db.select().from(favoritosTable).where(eq(favoritosTable.userId, userId)).orderBy(desc(favoritosTable.criadoEm)).limit(limit).offset(offset),
    db.select({ c: count() }).from(favoritosTable).where(eq(favoritosTable.userId, userId)),
  ]);
  const total = totalRows[0]?.c ?? 0;

  // Build response with embedded licitacao snapshot
  const result = await searchLicitacoes({ pagina: 1, tamanhoPagina: 50 });
  const licitacoesMap = new Map(result.data.map((l) => [l.id, l]));

  const data = rows.map((fav) => {
    const licitacao = licitacoesMap.get(fav.licitacaoId) ?? {
      id: fav.licitacaoId,
      numero: "-",
      ano: 0,
      modalidade: fav.licitacaoModalidade ?? "Pregão Eletrônico",
      modoDisputa: null,
      situacao: fav.licitacaoSituacao ?? "aberta",
      objeto: fav.licitacaoObjeto ?? "Licitação sem descrição",
      valorEstimado: fav.licitacaoValor ? parseFloat(fav.licitacaoValor) : null,
      orgaoNome: fav.licitacaoOrgao ?? "Órgão",
      orgaoCnpj: "",
      uf: fav.licitacaoUf ?? "",
      municipio: null,
      esfera: "",
      poder: "",
      dataAbertura: null,
      dataEncerramento: null,
      isFavoritada: true,
      criadoEm: fav.criadoEm.toISOString(),
    };
    return {
      id: fav.id,
      licitacaoId: fav.licitacaoId,
      nota: fav.nota ?? null,
      licitacao: { ...licitacao, isFavoritada: true },
      criadoEm: fav.criadoEm.toISOString(),
    };
  });

  res.json({ data, total, page, totalPages: Math.ceil(total / limit) });
});

router.post("/favoritos", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const { licitacaoId, nota } = req.body as { licitacaoId: string; nota?: string };

  if (!licitacaoId) {
    res.status(400).json({ error: "licitacaoId obrigatório" });
    return;
  }

  // Get licitação data for snapshot
  const result = await searchLicitacoes({ pagina: 1, tamanhoPagina: 50 });
  const licitacao = result.data.find((l) => l.id === licitacaoId);

  const [created] = await db
    .insert(favoritosTable)
    .values({
      userId,
      licitacaoId,
      nota: nota ?? null,
      licitacaoObjeto: licitacao?.objeto ?? null,
      licitacaoOrgao: licitacao?.orgaoNome ?? null,
      licitacaoUf: licitacao?.uf ?? null,
      licitacaoModalidade: licitacao?.modalidade ?? null,
      licitacaoSituacao: licitacao?.situacao ?? null,
      licitacaoValor: licitacao?.valorEstimado?.toString() ?? null,
    })
    .onConflictDoNothing()
    .returning();

  if (!created) {
    // already exists
    const existing = await db.select().from(favoritosTable)
      .where(and(eq(favoritosTable.userId, userId), eq(favoritosTable.licitacaoId, licitacaoId))).limit(1);
    const fav = existing[0]!;
    res.status(201).json({
      id: fav.id,
      licitacaoId: fav.licitacaoId,
      nota: fav.nota ?? null,
      licitacao: { ...licitacao, isFavoritada: true },
      criadoEm: fav.criadoEm.toISOString(),
    });
    return;
  }

  res.status(201).json({
    id: created.id,
    licitacaoId: created.licitacaoId,
    nota: created.nota ?? null,
    licitacao: { ...(licitacao ?? { id: licitacaoId }), isFavoritada: true },
    criadoEm: created.criadoEm.toISOString(),
  });
});

router.delete("/favoritos/:id", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw!, 10);

  await db.delete(favoritosTable).where(and(eq(favoritosTable.id, id), eq(favoritosTable.userId, userId)));
  res.json({ message: "Favorito removido com sucesso" });
});

export default router;
