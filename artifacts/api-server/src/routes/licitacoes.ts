import { Router } from "express";
import { requireAuth } from "../middlewares/auth";
import { searchLicitacoes, getLicitacaoItens, getLicitacaoDocumentos } from "../lib/pncp";
import { db, favoritosTable } from "@workspace/db";
import { and, eq } from "drizzle-orm";

const router = Router();

router.get("/licitacoes", requireAuth, async (req, res): Promise<void> => {
  const q = req.query;
  const page = parseInt(String(q.page ?? "1"), 10);
  const limit = parseInt(String(q.limit ?? "20"), 10);

  const result = await searchLicitacoes({
    q: q.q ? String(q.q) : undefined,
    modalidadeId: q.modalidade ? String(q.modalidade) : undefined,
    codigoUf: q.uf ? String(q.uf) : undefined,
    municipio: q.municipio ? String(q.municipio) : undefined,
    situacaoEdital: q.status ? String(q.status) : undefined,
    valorMin: q.valorMin ? parseFloat(String(q.valorMin)) : undefined,
    valorMax: q.valorMax ? parseFloat(String(q.valorMax)) : undefined,
    dataInicio: q.dataInicio ? String(q.dataInicio) : undefined,
    dataFim: q.dataFim ? String(q.dataFim) : undefined,
    esferaId: q.esfera ? String(q.esfera) : undefined,
    poderId: q.poder ? String(q.poder) : undefined,
    pagina: page,
    tamanhoPagina: limit,
  });

  const userId = req.session.userId!;
  const favs = await db.select({ licitacaoId: favoritosTable.licitacaoId }).from(favoritosTable).where(eq(favoritosTable.userId, userId));
  const favSet = new Set(favs.map((f) => f.licitacaoId));

  res.json({
    data: result.data.map((l) => ({ ...l, isFavoritada: favSet.has(l.id) })),
    total: result.total,
    page,
    totalPages: Math.ceil(result.total / limit),
  });
});

router.get("/licitacoes/:id", requireAuth, async (req, res): Promise<void> => {
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const userId = req.session.userId!;

  // Parse id: cnpj-ano-sequencial
  const parts = raw.split("-");
  if (parts.length < 3) {
    res.status(404).json({ error: "Licitação não encontrada" });
    return;
  }
  const sequencial = parseInt(parts[parts.length - 1]!, 10);
  const ano = parseInt(parts[parts.length - 2]!, 10);
  const cnpj = parts.slice(0, -2).join("-");

  // Search for this specific licitação
  const result = await searchLicitacoes({ pagina: 1, tamanhoPagina: 20 });
  const licitacao = result.data.find((l) => l.id === raw);

  if (!licitacao) {
    res.status(404).json({ error: "Licitação não encontrada" });
    return;
  }

  // Check if favorited
  const favs = await db.select({ id: favoritosTable.id }).from(favoritosTable)
    .where(and(eq(favoritosTable.userId, userId), eq(favoritosTable.licitacaoId, raw))).limit(1);
  const fav = favs[0];

  // Get items
  const itensRaw = await getLicitacaoItens(cnpj, ano, sequencial);
  const itens = itensRaw.map((item: Record<string, unknown>, idx: number) => ({
    id: idx + 1,
    numero: Number(item.numeroItem ?? idx + 1),
    descricao: String(item.descricao ?? item.descricaoItem ?? "Item sem descrição"),
    unidade: item.unidadeMedida ? String(item.unidadeMedida) : null,
    quantidade: item.quantidade != null ? Number(item.quantidade) : null,
    valorUnitario: item.valorUnitarioEstimado != null ? Number(item.valorUnitarioEstimado) : null,
    valorTotal: item.valorTotal != null ? Number(item.valorTotal) : null,
    categoria: item.categoria ? String(item.categoria) : null,
    situacao: item.situacao ? String(item.situacao) : null,
  }));

  res.json({
    ...licitacao,
    isFavoritada: !!fav,
    favoritoId: fav?.id ?? null,
    itens,
  });
});

router.get("/licitacoes/:id/itens", requireAuth, async (req, res): Promise<void> => {
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const parts = raw.split("-");
  const sequencial = parseInt(parts[parts.length - 1]!, 10);
  const ano = parseInt(parts[parts.length - 2]!, 10);
  const cnpj = parts.slice(0, -2).join("-");

  const itensRaw = await getLicitacaoItens(cnpj, ano, sequencial);
  const itens = itensRaw.map((item: Record<string, unknown>, idx: number) => ({
    id: idx + 1,
    numero: Number(item.numeroItem ?? idx + 1),
    descricao: String(item.descricao ?? item.descricaoItem ?? "Item"),
    unidade: item.unidadeMedida ? String(item.unidadeMedida) : null,
    quantidade: item.quantidade != null ? Number(item.quantidade) : null,
    valorUnitario: item.valorUnitarioEstimado != null ? Number(item.valorUnitarioEstimado) : null,
    valorTotal: item.valorTotal != null ? Number(item.valorTotal) : null,
    categoria: item.categoria ? String(item.categoria) : null,
    situacao: item.situacao ? String(item.situacao) : null,
  }));
  res.json(itens);
});

router.get("/licitacoes/:id/documentos-pncp", requireAuth, async (req, res): Promise<void> => {
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const parts = raw.split("-");
  const sequencial = parseInt(parts[parts.length - 1]!, 10);
  const ano = parseInt(parts[parts.length - 2]!, 10);
  const cnpj = parts.slice(0, -2).join("-");

  const docsRaw = await getLicitacaoDocumentos(cnpj, ano, sequencial);
  const docs = docsRaw.map((d: Record<string, unknown>, idx: number) => ({
    id: String(d.id ?? d.sequencialDocumento ?? idx + 1),
    titulo: String(d.titulo ?? d.nomeDocumento ?? "Documento"),
    tipo: String(d.tipoDocumento ?? d.tipo ?? "Documento"),
    url: String(d.uri ?? d.url ?? "#"),
    tamanho: d.tamanho != null ? Number(d.tamanho) : null,
    dataPublicacao: String(d.dataPublicacao ?? d.dataPublicacaoPncp ?? new Date().toISOString()),
  }));
  res.json(docs);
});

export default router;
