/**
 * PNCP (Portal Nacional de Contratações Públicas) API client
 * Docs: https://www.pncp.gov.br/api/pncp
 */

const PNCP_SEARCH_BASE = "https://pncp.gov.br/api/search/v1";
const PNCP_BASE = "https://pncp.gov.br/api/pncp/v1";

interface PncpSearchParams {
  q?: string;
  modalidadeId?: string;
  codigoUf?: string;
  municipio?: string;
  situacaoEdital?: string;
  valorMin?: number;
  valorMax?: number;
  dataInicio?: string;
  dataFim?: string;
  esferaId?: string;
  poderId?: string;
  pagina?: number;
  tamanhoPagina?: number;
}

interface PncpItem {
  numeroCompra?: string;
  anoCompra?: number;
  modalidadeNome?: string;
  modoDisputaNome?: string;
  situacaoCompraNome?: string;
  objetoCompra?: string;
  informacaoComplementar?: string;
  valorTotalEstimado?: number;
  orgaoEntidade?: {
    razaoSocial?: string;
    cnpj?: string;
  };
  unidadeOrgao?: {
    ufNome?: string;
    ufSigla?: string;
    municipioNome?: string;
  };
  esferaNome?: string;
  poderNome?: string;
  dataAberturaProposta?: string;
  dataEncerramentoProposta?: string;
  dataPublicacaoPncp?: string;
  linkSistemaOrigem?: string;
  sequencialCompra?: number;
  cnpjOrgao?: string;
}

function buildPncpId(item: PncpItem): string {
  const cnpj = item.orgaoEntidade?.cnpj ?? item.cnpjOrgao ?? "0";
  const ano = item.anoCompra ?? 0;
  const seq = item.sequencialCompra ?? 0;
  return `${cnpj.replace(/\D/g, "")}-${ano}-${seq}`;
}

function mapPncpSituacao(nome?: string): string {
  const n = (nome ?? "").toLowerCase();
  if (n.includes("encerrad") || n.includes("concluíd")) return "encerrada";
  if (n.includes("suspend")) return "suspensa";
  if (n.includes("cancel")) return "cancelada";
  if (n.includes("disput") || n.includes("andamento")) return "em_andamento";
  return "aberta";
}

export interface LicitacaoData {
  id: string;
  numero: string;
  ano: number;
  modalidade: string;
  modoDisputa: string | null;
  situacao: string;
  objeto: string;
  descricao: string | null;
  valorEstimado: number | null;
  orgaoNome: string;
  orgaoCnpj: string;
  orgaoUasg: string | null;
  uf: string;
  municipio: string | null;
  esfera: string;
  poder: string;
  dataAbertura: string | null;
  dataEncerramento: string | null;
  dataPublicacaoPncp: string | null;
  linkEdital: string | null;
  sequencial: number;
}

function mapPncpToLicitacao(item: PncpItem): LicitacaoData {
  const cnpj = item.orgaoEntidade?.cnpj ?? item.cnpjOrgao ?? "";
  const ano = item.anoCompra ?? 2024;
  const seq = item.sequencialCompra ?? 0;

  return {
    id: buildPncpId(item),
    numero: item.numeroCompra ?? String(seq),
    ano,
    modalidade: item.modalidadeNome ?? "Pregão Eletrônico",
    modoDisputa: item.modoDisputaNome ?? null,
    situacao: mapPncpSituacao(item.situacaoCompraNome),
    objeto: item.objetoCompra ?? "Sem descrição",
    descricao: item.informacaoComplementar ?? null,
    valorEstimado: item.valorTotalEstimado ?? null,
    orgaoNome: item.orgaoEntidade?.razaoSocial ?? "Órgão Desconhecido",
    orgaoCnpj: cnpj,
    orgaoUasg: null,
    uf: item.unidadeOrgao?.ufSigla ?? "",
    municipio: item.unidadeOrgao?.municipioNome ?? null,
    esfera: item.esferaNome ?? "Desconhecida",
    poder: item.poderNome ?? "Desconhecido",
    dataAbertura: item.dataAberturaProposta ?? null,
    dataEncerramento: item.dataEncerramentoProposta ?? null,
    dataPublicacaoPncp: item.dataPublicacaoPncp ?? null,
    linkEdital: item.linkSistemaOrigem ?? null,
    sequencial: seq,
  };
}

export async function searchLicitacoes(
  params: PncpSearchParams,
): Promise<{ data: LicitacaoData[]; total: number }> {
  const q = new URLSearchParams();
  if (params.q) q.set("q", params.q);
  if (params.modalidadeId) q.set("modalidadeId", params.modalidadeId);
  if (params.codigoUf) q.set("codigoUf", params.codigoUf);
  if (params.municipio) q.set("municipioNome", params.municipio);
  if (params.situacaoEdital) q.set("situacaoEdital", params.situacaoEdital);
  if (params.valorMin != null) q.set("valorTotalEstimadoDe", String(params.valorMin));
  if (params.valorMax != null) q.set("valorTotalEstimadoAte", String(params.valorMax));
  if (params.dataInicio) q.set("dataAberturaProposta", params.dataInicio);
  if (params.dataFim) q.set("dataEncerramentoProposta", params.dataFim);
  if (params.esferaId) q.set("esferaId", params.esferaId);
  if (params.poderId) q.set("poderId", params.poderId);
  q.set("pagina", String(params.pagina ?? 1));
  q.set("tamanhoPagina", String(params.tamanhoPagina ?? 20));

  try {
    const res = await fetch(`${PNCP_SEARCH_BASE}/contratatacoes/publicacao?${q.toString()}`, {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) throw new Error(`PNCP ${res.status}`);
    const json = (await res.json()) as {
      data?: PncpItem[];
      totalRegistros?: number;
    };
    const items = json.data ?? [];
    return {
      data: items.map(mapPncpToLicitacao),
      total: json.totalRegistros ?? items.length,
    };
  } catch {
    // Return mock data if PNCP is unavailable
    return getMockLicitacoes(params);
  }
}

export async function getLicitacaoItens(
  cnpj: string,
  ano: number,
  sequencial: number,
): Promise<object[]> {
  try {
    const cnpjClean = cnpj.replace(/\D/g, "");
    const res = await fetch(
      `${PNCP_BASE}/orgaos/${cnpjClean}/compras/${ano}/${sequencial}/itens`,
      {
        headers: { Accept: "application/json" },
        signal: AbortSignal.timeout(8000),
      },
    );
    if (!res.ok) return [];
    const json = (await res.json()) as object[];
    return Array.isArray(json) ? json : [];
  } catch {
    return getMockItens();
  }
}

export async function getLicitacaoDocumentos(
  cnpj: string,
  ano: number,
  sequencial: number,
): Promise<object[]> {
  try {
    const cnpjClean = cnpj.replace(/\D/g, "");
    const res = await fetch(
      `${PNCP_BASE}/orgaos/${cnpjClean}/compras/${ano}/${sequencial}/arquivos`,
      {
        headers: { Accept: "application/json" },
        signal: AbortSignal.timeout(8000),
      },
    );
    if (!res.ok) return [];
    const json = (await res.json()) as object[];
    return Array.isArray(json) ? json : [];
  } catch {
    return getMockDocumentos();
  }
}

// ── Mock data fallbacks ────────────────────────────────────────────────────────

const MOCK_LICITACOES: LicitacaoData[] = [
  {
    id: "00394544000854-2024-1",
    numero: "001/2024",
    ano: 2024,
    modalidade: "Pregão Eletrônico",
    modoDisputa: "Aberto",
    situacao: "aberta",
    objeto: "Aquisição de equipamentos de informática para modernização do parque tecnológico",
    descricao: "Inclui computadores, notebooks, monitores e periféricos",
    valorEstimado: 1850000,
    orgaoNome: "Ministério da Saúde",
    orgaoCnpj: "00394544000854",
    orgaoUasg: "250005",
    uf: "DF",
    municipio: "Brasília",
    esfera: "Federal",
    poder: "Executivo",
    dataAbertura: "2024-08-15T10:00:00Z",
    dataEncerramento: "2024-08-30T17:00:00Z",
    dataPublicacaoPncp: "2024-08-01T09:00:00Z",
    linkEdital: null,
    sequencial: 1,
  },
  {
    id: "08807461000174-2024-2",
    numero: "045/2024",
    ano: 2024,
    modalidade: "Concorrência",
    modoDisputa: "Fechado",
    situacao: "aberta",
    objeto: "Construção de UBS — Unidade Básica de Saúde no Município de Campinas",
    descricao: "Obra civil de construção de UBS com 800m²",
    valorEstimado: 3200000,
    orgaoNome: "Prefeitura Municipal de Campinas",
    orgaoCnpj: "08807461000174",
    orgaoUasg: null,
    uf: "SP",
    municipio: "Campinas",
    esfera: "Municipal",
    poder: "Executivo",
    dataAbertura: "2024-09-10T09:00:00Z",
    dataEncerramento: "2024-10-10T17:00:00Z",
    dataPublicacaoPncp: "2024-08-20T08:00:00Z",
    linkEdital: null,
    sequencial: 2,
  },
  {
    id: "86969908000128-2024-3",
    numero: "012/2024",
    ano: 2024,
    modalidade: "Pregão Eletrônico",
    modoDisputa: "Aberto e Fechado",
    situacao: "em_andamento",
    objeto: "Contratação de serviços de limpeza e conservação predial para sedes regionais",
    descricao: "Serviços continuados com dedicação exclusiva de mão de obra",
    valorEstimado: 720000,
    orgaoNome: "TRF — Tribunal Regional Federal 3ª Região",
    orgaoCnpj: "86969908000128",
    orgaoUasg: "090032",
    uf: "SP",
    municipio: "São Paulo",
    esfera: "Federal",
    poder: "Judiciário",
    dataAbertura: "2024-07-20T10:00:00Z",
    dataEncerramento: "2024-07-20T14:00:00Z",
    dataPublicacaoPncp: "2024-07-05T08:00:00Z",
    linkEdital: null,
    sequencial: 3,
  },
  {
    id: "28152650000128-2024-4",
    numero: "023/2024",
    ano: 2024,
    modalidade: "Dispensa Eletrônica",
    modoDisputa: "Aberto",
    situacao: "encerrada",
    objeto: "Aquisição de material de expediente e papelaria",
    descricao: "Material de escritório para suprimento do estoque",
    valorEstimado: 45000,
    orgaoNome: "Assembleia Legislativa do Estado do Rio de Janeiro",
    orgaoCnpj: "28152650000128",
    orgaoUasg: null,
    uf: "RJ",
    municipio: "Rio de Janeiro",
    esfera: "Estadual",
    poder: "Legislativo",
    dataAbertura: "2024-06-01T08:00:00Z",
    dataEncerramento: "2024-06-15T18:00:00Z",
    dataPublicacaoPncp: "2024-05-25T09:00:00Z",
    linkEdital: null,
    sequencial: 4,
  },
  {
    id: "00394544000854-2024-5",
    numero: "078/2024",
    ano: 2024,
    modalidade: "Pregão Eletrônico",
    modoDisputa: "Aberto",
    situacao: "aberta",
    objeto: "Fornecimento de medicamentos e insumos hospitalares para a Farmácia Básica",
    descricao: "Medicamentos da RENAME e insumos para farmácias municipais",
    valorEstimado: 5600000,
    orgaoNome: "Secretaria de Saúde do Estado de Minas Gerais",
    orgaoCnpj: "18715139000129",
    orgaoUasg: null,
    uf: "MG",
    municipio: "Belo Horizonte",
    esfera: "Estadual",
    poder: "Executivo",
    dataAbertura: "2024-09-05T10:00:00Z",
    dataEncerramento: "2024-09-20T17:00:00Z",
    dataPublicacaoPncp: "2024-08-25T08:00:00Z",
    linkEdital: null,
    sequencial: 5,
  },
  {
    id: "10544193000152-2024-6",
    numero: "003/2024",
    ano: 2024,
    modalidade: "Tomada de Preços",
    modoDisputa: "Fechado",
    situacao: "aberta",
    objeto: "Reforma e ampliação da Escola Municipal João Pessoa — pavimentação e pintura",
    descricao: "Obras de reforma geral incluindo telhado, instalações elétricas e hidráulicas",
    valorEstimado: 890000,
    orgaoNome: "Prefeitura Municipal de Fortaleza",
    orgaoCnpj: "10544193000152",
    orgaoUasg: null,
    uf: "CE",
    municipio: "Fortaleza",
    esfera: "Municipal",
    poder: "Executivo",
    dataAbertura: "2024-08-28T09:00:00Z",
    dataEncerramento: "2024-09-28T18:00:00Z",
    dataPublicacaoPncp: "2024-08-10T08:00:00Z",
    linkEdital: null,
    sequencial: 6,
  },
];

function getMockLicitacoes(params: PncpSearchParams): { data: LicitacaoData[]; total: number } {
  let results = [...MOCK_LICITACOES];
  if (params.q) {
    const q = params.q.toLowerCase();
    results = results.filter(
      (l) =>
        l.objeto.toLowerCase().includes(q) ||
        l.orgaoNome.toLowerCase().includes(q),
    );
  }
  if (params.codigoUf) {
    results = results.filter((l) => l.uf === params.codigoUf);
  }
  const page = params.pagina ?? 1;
  const limit = params.tamanhoPagina ?? 20;
  const start = (page - 1) * limit;
  return {
    data: results.slice(start, start + limit),
    total: results.length,
  };
}

function getMockItens(): object[] {
  return [
    {
      id: 1,
      numero: 1,
      descricao: "Computador Desktop — Intel Core i7, 16GB RAM, SSD 512GB",
      unidade: "UN",
      quantidade: 50,
      valorUnitario: 4500,
      valorTotal: 225000,
      categoria: "Tecnologia da Informação",
      situacao: "Aberto",
    },
    {
      id: 2,
      numero: 2,
      descricao: "Monitor LED 24 polegadas Full HD",
      unidade: "UN",
      quantidade: 50,
      valorUnitario: 1200,
      valorTotal: 60000,
      categoria: "Tecnologia da Informação",
      situacao: "Aberto",
    },
    {
      id: 3,
      numero: 3,
      descricao: "Notebook — Intel Core i5, 8GB RAM, SSD 256GB",
      unidade: "UN",
      quantidade: 20,
      valorUnitario: 3800,
      valorTotal: 76000,
      categoria: "Tecnologia da Informação",
      situacao: "Aberto",
    },
  ];
}

function getMockDocumentos(): object[] {
  return [
    {
      id: "doc-001",
      titulo: "Edital de Licitação",
      tipo: "Edital",
      url: "#",
      tamanho: 524288,
      dataPublicacao: "2024-08-01T09:00:00Z",
    },
    {
      id: "doc-002",
      titulo: "Termo de Referência",
      tipo: "Anexo",
      url: "#",
      tamanho: 245760,
      dataPublicacao: "2024-08-01T09:00:00Z",
    },
    {
      id: "doc-003",
      titulo: "Minuta do Contrato",
      tipo: "Anexo",
      url: "#",
      tamanho: 196608,
      dataPublicacao: "2024-08-01T09:00:00Z",
    },
  ];
}

export { MOCK_LICITACOES };
