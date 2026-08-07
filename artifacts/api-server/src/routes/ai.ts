import { Router } from "express";
import { requireAuth } from "../middlewares/auth";
import { searchLicitacoes, MOCK_LICITACOES } from "../lib/pncp";

const router = Router();

router.post("/ai/search", requireAuth, async (req, res): Promise<void> => {
  const { query } = req.body as { query?: string; contexto?: string };

  if (!query || query.length < 3) {
    res.status(400).json({ error: "Query deve ter pelo menos 3 caracteres" });
    return;
  }

  // Parse natural language query to extract filters
  const q = query.toLowerCase();

  const ufs: string[] = [];
  const estados: Record<string, string> = {
    "são paulo": "SP", "sao paulo": "SP",
    "rio de janeiro": "RJ",
    "minas gerais": "MG",
    "bahia": "BA",
    "paraná": "PR", "parana": "PR",
    "rio grande do sul": "RS",
    "santa catarina": "SC",
    "goiás": "GO", "goias": "GO",
    "mato grosso": "MT",
    "pará": "PA", "para": "PA",
    "ceará": "CE", "ceara": "CE",
    "pernambuco": "PE",
    "amazonas": "AM",
    "maranhão": "MA", "maranhao": "MA",
    "espírito santo": "ES", "espirito santo": "ES",
    "distrito federal": "DF",
    "brasília": "DF", "brasilia": "DF",
  };
  for (const [nome, sigla] of Object.entries(estados)) {
    if (q.includes(nome)) ufs.push(sigla);
  }

  let valorMin: number | null = null;
  let valorMax: number | null = null;
  const valorMatch = q.match(/(\d+(?:[.,]\d+)?)\s*(?:mil|k|mi(?:lhões?|lhao)?)/i);
  if (valorMatch) {
    const val = parseFloat(valorMatch[1]!.replace(",", "."));
    if (q.includes("mil") || q.includes(" k")) valorMin = val * 1000;
    if (q.includes("mi")) valorMin = val * 1000000;
  }

  const modalidades: string[] = [];
  if (q.includes("pregão") || q.includes("pregao")) modalidades.push("Pregão Eletrônico");
  if (q.includes("concorrência") || q.includes("concorrencia")) modalidades.push("Concorrência");
  if (q.includes("dispensa")) modalidades.push("Dispensa Eletrônica");
  if (q.includes("tomada")) modalidades.push("Tomada de Preços");

  // Extract keywords (remove common words)
  const stopWords = new Set(["de", "do", "da", "dos", "das", "para", "com", "em", "no", "na", "por", "ou", "e", "que", "uma", "um", "as", "os", "ao", "mais"]);
  const palavrasChave = query
    .split(/\s+/)
    .filter((w) => w.length > 3 && !stopWords.has(w.toLowerCase()))
    .slice(0, 5);

  // Search with extracted filters
  const searchQ = palavrasChave.join(" ") || query;
  const result = await searchLicitacoes({
    q: searchQ,
    codigoUf: ufs[0],
    valorMin: valorMin ?? undefined,
    valorMax: valorMax ?? undefined,
    pagina: 1,
    tamanhoPagina: 10,
  });

  // Build human-readable interpretation
  const parts = [`Busquei por licitações relacionadas a "${palavrasChave.join(", ") || query}"`];
  if (ufs.length > 0) parts.push(`no estado ${ufs.join(", ")}`);
  if (valorMin) parts.push(`com valor acima de R$ ${valorMin.toLocaleString("pt-BR")}`);
  if (modalidades.length > 0) parts.push(`modalidade ${modalidades.join(" ou ")}`);
  const interpretacao = parts.join(", ") + ".";

  res.json({
    query,
    interpretacao,
    filtrosGerados: {
      palavrasChave,
      modalidades,
      ufs,
      valorMin,
      valorMax,
    },
    resultados: result.data.map((l) => ({ ...l, isFavoritada: false })),
    totalEncontrados: result.total,
  });
});

router.get("/ai/sugestoes", requireAuth, async (req, res): Promise<void> => {
  // Return top licitações as personalized suggestions
  const result = await searchLicitacoes({ pagina: 1, tamanhoPagina: 6 });
  res.json(result.data.map((l) => ({ ...l, isFavoritada: false })));
});

export default router;
