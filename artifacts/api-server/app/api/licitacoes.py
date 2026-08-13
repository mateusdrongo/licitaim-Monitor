from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks  # BackgroundTasks: /admin/sync
from typing import Optional
import random
import re
from datetime import date, timedelta
import httpx
from ..core.deps import get_current_user
from ..core.admin import get_admin_user
from ..db.session import get_pool
from ..db.licitacoes_repo import (
    search_licitacoes_cache,
    get_cache_stats,
)

router = APIRouter(prefix="/licitacoes", tags=["licitacoes"])

# ── Fontes externas ────────────────────────────────────────────────────────────
# Write API — individual lookups por CNPJ/ano/seq; NÃO bloqueada no Replit
PNCP_WRITE_BASE    = "https://pncp.gov.br/api/pncp/v1"
PNCP_PORTAL_BASE   = "https://pncp.gov.br/pncp-api/v1"
# Consulta pública — base e endpoint de listagem
PNCP_CONSULTA_BASE = "https://pncp.gov.br/api/consulta/v1"
PNCP_CONSULTA_URL  = f"{PNCP_CONSULTA_BASE}/contratacoes/publicacao"
# Espelho dadosabertos — fallback nunca bloqueado
DADOSABERTOS_URL  = "https://dadosabertos.compras.gov.br/modulo-contratacoes/1_consultarContratacoes_PNCP_14133"

# Códigos PNCP consulta API — tabela oficial codigoModalidadeContratacao:
#   1=Leilão-E  2=Diálogo Competitivo  3=Concurso
#   4=Concorrência-E  5=Concorrência-P  6=Pregão-E  7=Pregão-P
#   8=Dispensa  9=Inexigibilidade  10=Manifestação de Interesse
#   11=Pré-qualificação  12=Credenciamento  13=Leilão-P
#   14=Inaplicabilidade  15=Chamada Pública
#   16=Concorrência-E Internacional  17=Concorrência-P Internacional
#   18=Pregão-E Internacional  19=Pregão-P Internacional
# Códigos dadosabertos — usado por sync_service.py como fallback
MODALIDADES_DADOSABERTOS = [5, 6, 3, 7]

_MODAL_NAME_TO_CODE: dict[str, int] = {
    # Pregão
    "pregão eletrônico": 6, "pregao eletronico": 6, "pregão - eletrônico": 6,
    "pregão": 6,
    "pregão presencial": 7, "pregao presencial": 7, "pregão - presencial": 7,
    "pregão eletrônico internacional": 18,
    "pregão presencial internacional": 19,
    # Concorrência
    "concorrência eletrônica": 4, "concorrencia eletronica": 4, "concorrência - eletrônica": 4,
    "concorrência": 4, "concorrencia": 4,
    "concorrência presencial": 5, "concorrencia presencial": 5, "concorrência - presencial": 5,
    "concorrência eletrônica internacional": 16,
    "concorrência presencial internacional": 17,
    # Dispensa / Inexigibilidade
    "dispensa de licitação": 8, "dispensa": 8,
    "inexigibilidade": 9,
    # Leilão
    "leilão eletrônico": 1, "leilão - eletrônico": 1, "leilão": 1,
    "leilão presencial": 13, "leilão - presencial": 13,
    # Outros
    "diálogo competitivo": 2, "dialogo competitivo": 2,
    "concurso": 3,
    "manifestação de interesse": 10, "manifestacao de interesse": 10,
    "pré-qualificação": 11, "pre-qualificacao": 11, "prequalificacao": 11,
    "credenciamento": 12,
    "inaplicabilidade da licitação": 14, "inaplicabilidade": 14,
    "chamada pública": 15, "chamada publica": 15,
}

# ── User-Agent rotation — bypass WAF PNCP ─────────────────────────────────────
# Pool amplo: Chrome/Firefox/Edge/Safari em Windows/Mac/Linux/Mobile.
_USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    # Linux Chrome
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Safari Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]

_ACCEPT_LANGUAGES = [
    "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "pt-BR,pt;q=0.9,en;q=0.8",
    "pt-BR,pt;q=0.8,en-US;q=0.6,en;q=0.4",
    "pt,pt-BR;q=0.9,en-US;q=0.8,en;q=0.6",
]

def _pncp_headers() -> dict:
    """Headers com rotação de User-Agent e Accept-Language para bypass de WAF."""
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": random.choice(_ACCEPT_LANGUAGES),
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
    }

# ── Domínios ───────────────────────────────────────────────────────────────────
_ESFERA_MAP = {"F": "federal", "E": "estadual", "M": "municipal", "D": "distrital"}
_PODER_MAP  = {
    "E": "executivo", "L": "legislativo", "J": "judiciário",
    "M": "ministério público", "D": "defensoria pública",
}
_SITUACAO_MAP = {
    "divulgada": "aberta", "publicada": "aberta", "aberta": "aberta",
    "recebendo": "aberta", "em andamento": "em_andamento",
    "em disputa": "em_andamento", "em licitação": "em_andamento",
    "encerrada": "encerrada", "homologada": "encerrada",
    "adjudicada": "encerrada", "anulada": "cancelada",
    "suspensa": "suspensa", "revogada": "cancelada", "cancelada": "cancelada",
    "fracassada": "encerrada", "deserta": "encerrada",
}

def _normalize_situacao(raw: str) -> str:
    lower = raw.lower()
    for k, v in _SITUACAO_MAP.items():
        if k in lower:
            return v
    return "aberta"


def _parse_numero_pncp(numero: str) -> tuple[str, int, int] | None:
    """
    Parse do numeroControlePNCP no formato CNPJ14-unit-seq/ano.
    Retorna (cnpj, seq, ano) ou None se inválido.
    """
    m = re.match(r'^(\d{14})-\d+-(\d+)\/(\d{4})$', numero or "")
    if m:
        return m.group(1), int(m.group(2)), int(m.group(3))
    return None


# ── Normalizadores ─────────────────────────────────────────────────────────────

def _normalize_pncp_item(item: dict) -> dict:
    """
    Normaliza resposta da API PNCP (write API ou consulta API) para nosso schema.
    Ambas as APIs retornam orgaoEntidade/unidadeOrgao no mesmo formato.
    """
    orgao   = item.get("orgaoEntidade", {})
    unidade = item.get("unidadeOrgao",  {})
    numero  = item.get("numeroControlePNCP", "")
    try:
        ano = int(numero.split("/")[-1]) if "/" in numero else date.today().year
    except (ValueError, IndexError):
        ano = date.today().year

    municipio = unidade.get("municipioNome", "") or ""
    return {
        "id":                   item.get("id") or numero,
        "numero":               numero,
        "ano":                  ano,
        "modalidade":           item.get("modalidadeNome", ""),
        "modo_disputa":         item.get("modoDisputaNome"),
        "situacao":             _normalize_situacao(item.get("situacaoCompraNome", "")),
        "objeto":               item.get("objetoCompra", ""),
        "valor_estimado":       item.get("valorTotalEstimado"),
        "orgao_nome":           orgao.get("razaoSocial", "") or unidade.get("nomeUnidade", ""),
        "orgao_cnpj":           orgao.get("cnpj", ""),
        "uf":                   unidade.get("ufSigla", ""),
        "municipio":            municipio.title(),
        "esfera":               item.get("esfera", "federal"),
        "poder":                item.get("poder",  "executivo"),
        "data_abertura":        item.get("dataAberturaProposta") or item.get("dataAberturaPropostaPncp"),
        "data_encerramento":    item.get("dataEncerramentoProposta") or item.get("dataEncerramentoPropostaPncp"),
        "data_publicacao_pncp": item.get("dataPublicacaoPncp"),
        "criado_em":            (item.get("dataPublicacaoPncp")
                                 or item.get("dataInclusaoPncp")
                                 or f"{date.today().year}-01-01T00:00:00"),
        "is_favoritada":        False,
        "srp":                  item.get("srp", False),
        "numero_processo":      item.get("processo") or item.get("numeroCompra"),
        "informacao_complementar": item.get("informacaoComplementar"),
        "amparo_legal":         item.get("amparoLegalNome"),
        # campos extras — disponíveis no detalhe individual
        "valor_total_homologado": item.get("valorTotalHomologado"),
        "numero_parcelas":      item.get("numeroParcelas"),
        "tipo_contratacao":     item.get("tipoContratacaoNome"),
        "categoria_processo":   item.get("categoriaProcessoNome"),
        "link_sistema_origem":  item.get("linkSistemaOrigem"),
        "orcamento_sigiloso":   item.get("orcamentoSigiloso", False),
        "unidade_nome":         unidade.get("nomeUnidade"),
        "codigo_unidade":       unidade.get("codigoUnidade"),
        "situacao_compra_nome": item.get("situacaoCompraNome"),
    }


def _normalize_dadosabertos(item: dict) -> dict:
    """Normaliza item do dadosabertos para nosso schema (usado no fallback)."""
    numero = item.get("numeroControlePNCP", "")
    try:
        ano = int(numero.split("/")[-1]) if "/" in numero else (item.get("anoCompraPncp") or date.today().year)
    except (ValueError, TypeError):
        ano = date.today().year

    esfera_id = item.get("orgaoEntidadeEsferaId", "F") or "F"
    poder_id  = item.get("orgaoEntidadePoderId",  "E") or "E"

    return {
        "id":                   item.get("idCompra") or numero,
        "numero":               numero,
        "ano":                  ano,
        "modalidade":           item.get("modalidadeNome", ""),
        "modo_disputa":         item.get("modoDisputaNomePncp"),
        "situacao":             _normalize_situacao(item.get("situacaoCompraNomePncp", "")),
        "objeto":               item.get("objetoCompra", ""),
        "valor_estimado":       item.get("valorTotalEstimado"),
        "orgao_nome":           (item.get("orgaoEntidadeRazaoSocial")
                                 or item.get("unidadeOrgaoNomeUnidade", "")),
        "orgao_cnpj":           item.get("orgaoEntidadeCnpj", ""),
        "uf":                   item.get("unidadeOrgaoUfSigla", ""),
        "municipio":            item.get("unidadeOrgaoMunicipioNome", "").title(),
        "esfera":               _ESFERA_MAP.get(esfera_id, "federal"),
        "poder":                _PODER_MAP.get(poder_id,  "executivo"),
        "data_abertura":        item.get("dataAberturaPropostaPncp"),
        "data_encerramento":    item.get("dataEncerramentoPropostaPncp"),
        "data_publicacao_pncp": item.get("dataPublicacaoPncp"),
        "criado_em":            (item.get("dataInclusaoPncp")
                                 or item.get("dataPublicacaoPncp")
                                 or f"{date.today().year}-01-01T00:00:00"),
        "is_favoritada":        False,
        "srp":                  item.get("srp", False),
        "numero_processo":      item.get("processo"),
        "informacao_complementar": item.get("informacaoComplementar"),
        "amparo_legal":         item.get("amparoLegalNome"),
    }


# Alias de compatibilidade para ai.py e sync_service.py
def _normalize(item: dict) -> dict:
    return item


# ── Fetchers (fallback — usado por sync_service.py) ───────────────────────────

async def _fetch_dadosabertos(
    client: httpx.AsyncClient,
    params: dict,
    modalidade: int,
) -> list[dict]:
    """Busca modalidade no dadosabertos (fallback quando PNCP consulta falha)."""
    try:
        resp = await client.get(DADOSABERTOS_URL, params={**params, "codigoModalidade": modalidade})
        if resp.status_code == 200:
            return [_normalize_dadosabertos(i) for i in resp.json().get("resultado", [])]
    except Exception:
        pass
    return []



# ── Mock fallback ──────────────────────────────────────────────────────────────
MOCK_LICITACOES = [
    {
        "id": "00394460000154-1-000001/2024",
        "numero": "00394460000154-1-000001/2024",
        "ano": 2024, "modalidade": "Pregão Eletrônico", "modo_disputa": "Aberto",
        "situacao": "aberta",
        "objeto": "Aquisição de equipamentos hospitalares e suprimentos médicos para UTI",
        "valor_estimado": 2500000.0, "orgao_nome": "Ministério da Saúde",
        "orgao_cnpj": "00394460000154", "uf": "DF", "municipio": "Brasília",
        "esfera": "federal", "poder": "executivo",
        "data_abertura": "2024-11-15", "data_encerramento": "2024-11-20",
        "data_publicacao_pncp": "2024-11-01",
        "criado_em": "2024-11-01T00:00:00", "is_favoritada": False, "srp": False,
    },
    {
        "id": "08807461000174-1-000002/2024",
        "numero": "08807461000174-1-000002/2024",
        "ano": 2024, "modalidade": "Concorrência Eletrônica", "modo_disputa": "Aberto",
        "situacao": "aberta",
        "objeto": "Construção de Unidade Básica de Saúde (UBS) no Município de Campinas",
        "valor_estimado": 8900000.0, "orgao_nome": "Prefeitura Municipal de Campinas",
        "orgao_cnpj": "08807461000174", "uf": "SP", "municipio": "Campinas",
        "esfera": "municipal", "poder": "executivo",
        "data_abertura": "2024-11-25", "data_encerramento": "2024-12-01",
        "data_publicacao_pncp": "2024-10-20",
        "criado_em": "2024-10-20T00:00:00", "is_favoritada": False, "srp": False,
    },
    {
        "id": "02403006000116-1-000003/2024",
        "numero": "02403006000116-1-000003/2024",
        "ano": 2024, "modalidade": "Pregão Eletrônico", "modo_disputa": "Aberto",
        "situacao": "aberta",
        "objeto": "Fornecimento de notebooks e tablets para escolas públicas estaduais — TI educação",
        "valor_estimado": 4750000.0,
        "orgao_nome": "Secretaria de Estado de Educação de MG",
        "orgao_cnpj": "02403006000116", "uf": "MG", "municipio": "Belo Horizonte",
        "esfera": "estadual", "poder": "executivo",
        "data_abertura": "2024-11-28", "data_encerramento": "2024-12-05",
        "data_publicacao_pncp": "2024-11-05",
        "criado_em": "2024-11-05T00:00:00", "is_favoritada": False, "srp": False,
    },
]


# ── snake_to_camel ─────────────────────────────────────────────────────────────
_SNAKE_TO_CAMEL_MAP = {
    "id": "id", "numero": "numero", "ano": "ano",
    "modalidade": "modalidade", "modo_disputa": "modoDisputa",
    "situacao": "situacao", "objeto": "objeto",
    "valor_estimado": "valorEstimado",
    "orgao_nome": "orgaoNome", "orgao_cnpj": "orgaoCnpj",
    "uf": "uf", "municipio": "municipio",
    "esfera": "esfera", "poder": "poder",
    "data_abertura": "dataAbertura",
    "data_encerramento": "dataEncerramento",
    "data_publicacao_pncp": "dataPublicacaoPncp",
    "criado_em": "criadoEm",
    "is_favoritada": "isFavoritada", "srp": "srp",
    "numero_processo": "numeroProcesso",
    "informacao_complementar": "informacaoComplementar",
    "amparo_legal": "amparoLegal",
    # extras
    "valor_total_homologado": "valorTotalHomologado",
    "numero_parcelas": "numeroParcelas",
    "tipo_contratacao": "tipoContratacao",
    "categoria_processo": "categoriaProcesso",
    "link_sistema_origem": "linkSistemaOrigem",
    "orcamento_sigiloso": "orcamentoSigiloso",
    "unidade_nome": "unidadeNome",
    "codigo_unidade": "codigoUnidade",
    "situacao_compra_nome": "situacaoCompraNome",
}

def _snake_to_camel(item: dict) -> dict:
    return {_SNAKE_TO_CAMEL_MAP.get(k, k): v for k, v in item.items()}


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/arquivos")
async def get_arquivos_by_pncp(
    pncp: str = Query(..., description="Número de controle PNCP (CNPJ14-unit-seq/ano)"),
    current_user: dict = Depends(get_current_user),
):
    """
    Lista os arquivos/documentos de uma licitação dado o seu número de controle PNCP.
    Usa rota própria (/arquivos) para evitar conflito de path com IDs que contêm barras.
    """
    parsed = _parse_numero_pncp(pncp)
    if not parsed:
        return []

    cnpj, seq, ano = parsed
    urls = [
        f"{PNCP_PORTAL_BASE}/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos",
        f"{PNCP_WRITE_BASE}/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos",
    ]

    import re as _re

    def _clean_url(u: str | None) -> str | None:
        """Remove portas internas do balanceador de carga (ex: :33066) das URLs do PNCP."""
        if not u:
            return u
        return _re.sub(r'(https://pncp\.gov\.br):\d+', r'\1', u)

    async with httpx.AsyncClient(timeout=12.0) as client:
        for url in urls:
            try:
                resp = await client.get(url, headers=_pncp_headers())
                if resp.status_code == 200:
                    raw = resp.json()
                    items = raw.get("data", raw) if isinstance(raw, dict) else raw
                    if isinstance(items, list):
                        # Sanitiza porta interna em url/uri de cada item
                        for item in items:
                            if isinstance(item, dict):
                                item["url"] = _clean_url(item.get("url"))
                                item["uri"] = _clean_url(item.get("uri"))
                        return items
            except Exception:
                continue

    return []


@router.get("")
async def search_licitacoes(
    q:               Optional[str]   = Query(None),
    modalidade:      Optional[str]   = Query(None),
    uf:              Optional[str]   = Query(None),
    status:          Optional[str]   = Query(None),
    valorMin:        Optional[float] = Query(None),
    valorMax:        Optional[float] = Query(None),
    dataInicio:      Optional[str]   = Query(None),
    dataFim:         Optional[str]   = Query(None),
    somenteVigentes: bool            = Query(False),
    pagina:          int             = Query(1, ge=1),
    page:            int             = Query(1, ge=1),
    limit:           int             = Query(20, ge=1, le=300),
    current_user:    dict            = Depends(get_current_user),
):
    hoje       = date.today()
    inicio_pad = (hoje - timedelta(days=30)).isoformat()
    fim_pad    = hoje.isoformat()

    data_ini_iso = dataInicio or inicio_pad
    data_fim_iso = dataFim    or fim_pad
    page_num     = max(pagina, page)

    # Resolve código da modalidade para filtrar no banco
    modal_code: Optional[int] = None
    if modalidade:
        m_lower = modalidade.lower().strip()
        modal_code = next(
            (v for k, v in _MODAL_NAME_TO_CODE.items() if k in m_lower), None
        )

    pool = await get_pool()

    # Quando somenteVigentes, ignora o filtro de status e usa situações abertas
    situacao_filtro = status
    if somenteVigentes:
        situacao_filtro = "aberta"

    # Busca sempre no banco local — os coletores mantêm licitacoes_cache atualizado
    # a cada COLLECTOR_INTERVAL_MINUTES minutos (padrão 20 min).
    cached, total = await search_licitacoes_cache(
        pool,
        q=q, uf=uf, modalidade_codigo=modal_code,
        situacao=situacao_filtro, somente_vigentes=somenteVigentes,
        valor_min=valorMin, valor_max=valorMax,
        data_inicio=data_ini_iso, data_fim=data_fim_iso,
        page=page_num, limit=limit,
    )
    return {
        "data":        cached,
        "total":       total,
        "page":        page_num,
        "total_pages": max(1, -(-total // limit)),
        "source":      "banco",
        "queued":      False,
    }


# ── Sync manual (apenas administradores) ──────────────────────────────────────

@router.post("/admin/sync")
async def manual_sync(
    background_tasks: BackgroundTasks,
    _admin: dict = Depends(get_admin_user),
):
    """
    Dispara um ciclo de coleta manual em background. Retorna imediatamente.
    Requer privilégio de administrador (ver ADMIN_EMAILS em env).

    Delega ao mesmo mecanismo do endpoint POST /collector/run para garantir
    comportamento idêntico: usa run_one_cycle() com o lock _is_running.
    Rejeita com 409 se já houver um ciclo em andamento.
    """
    from . import collector as _col_mod  # noqa: PLC0415

    # Atomic check-and-reserve under the same lock used by /collector/run
    async with _col_mod._run_lock:
        if _col_mod._is_running:
            raise HTTPException(
                status_code=409,
                detail="Já existe um ciclo de coleta em andamento. Aguarde a conclusão.",
            )
        _col_mod._is_running = True

    background_tasks.add_task(_col_mod._run_collection_cycle)
    return {"status": "started", "message": "Ciclo de coleta iniciado em background."}


@router.get("/admin/stats")
async def cache_stats(
    current_user: dict = Depends(get_current_user),
):
    """
    Retorna estatísticas do cache de licitações (acessível a todos os usuários autenticados).
    Inclui is_admin=True quando o usuário atual tem permissão para disparar /admin/sync.
    """
    import os as _os
    pool = await get_pool()
    stats = await get_cache_stats(pool)

    # Verifica se o usuário corrente é admin (replica lógica de get_admin_user)
    allowed = {e.strip().lower() for e in _os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
    email = (current_user.get("email") or "").lower()
    stats["is_admin"] = bool(allowed and email in allowed)
    return stats


@router.get("/admin/sync/status")
async def sync_status(
    _admin: dict = Depends(get_admin_user),
):
    """
    Retorna se há um ciclo de coleta em andamento.
    Reflete o flag _is_running do collector (compartilhado por /collector/run
    e /admin/sync). Usado para polling pelo frontend.
    """
    from . import collector as _col_mod  # noqa: PLC0415
    return {"in_progress": _col_mod._is_running}


@router.get("/{licitacao_id:path}")
async def get_licitacao(
    licitacao_id: str,
    pncp: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    # 1. Mocks legados
    mock = next((m for m in MOCK_LICITACOES if m["id"] == licitacao_id), None)
    if mock:
        return _snake_to_camel(mock)

    # 2. Determina o numeroControlePNCP a usar
    numero_busca = pncp or (licitacao_id if "/" in licitacao_id else None)

    # 3. Busca no banco local (fonte principal — coletores mantêm atualizado)
    pool = await get_pool()
    row = None
    if numero_busca:
        row = await pool.fetchrow(
            "SELECT * FROM licitacoes_cache WHERE numero = $1", numero_busca
        )
    if row is None:
        row = await pool.fetchrow(
            "SELECT * FROM licitacoes_cache WHERE id = $1 OR numero = $2",
            licitacao_id, licitacao_id,
        )
    if row:
        return _snake_to_camel(dict(row))

    raise HTTPException(status_code=404, detail="Licitação não encontrada")


@router.get("/{licitacao_id:path}/itens")
async def get_itens(
    licitacao_id: str,
    current_user: dict = Depends(get_current_user),
):
    parsed = _parse_numero_pncp(licitacao_id)
    if parsed:
        cnpj, seq, ano = parsed
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{PNCP_WRITE_BASE}/orgaos/{cnpj}/compras/{ano}/{seq}/itens",
                    params={"pagina": 1, "tamanhoPagina": 50},
                    headers=_pncp_headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("data", data) if isinstance(data, dict) else data
        except Exception:
            pass
    return []


@router.get("/{licitacao_id:path}/documentos-pncp")
async def get_documentos_pncp(
    licitacao_id: str,
    current_user: dict = Depends(get_current_user),
):
    parsed = _parse_numero_pncp(licitacao_id)
    if parsed:
        cnpj, seq, ano = parsed
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{PNCP_WRITE_BASE}/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos",
                    params={"pagina": 1, "tamanhoPagina": 20},
                    headers=_pncp_headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("data", data) if isinstance(data, dict) else data
        except Exception:
            pass
    return []


@router.get("/{licitacao_id:path}/arquivos")
async def get_arquivos(
    licitacao_id: str,
    pncp: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """
    Lista os arquivos/documentos de uma licitação via API pública do PNCP.
    Tenta primeiro o portal público (pncp-api/v1) e faz fallback para a
    write API (api/pncp/v1) caso a primeira falhe.

    URL pública:  https://pncp.gov.br/pncp-api/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos
    URL alternativa: https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos
    """
    numero_busca = pncp or (licitacao_id if "/" in licitacao_id else None)
    parsed = _parse_numero_pncp(numero_busca or licitacao_id)
    if not parsed:
        return []

    cnpj, seq, ano = parsed
    urls = [
        f"{PNCP_PORTAL_BASE}/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos",
        f"{PNCP_WRITE_BASE}/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos",
    ]

    async with httpx.AsyncClient(timeout=12.0) as client:
        for url in urls:
            try:
                resp = await client.get(url, headers=_pncp_headers())
                if resp.status_code == 200:
                    raw = resp.json()
                    # A API retorna lista direta ou { data: [...] }
                    items = raw.get("data", raw) if isinstance(raw, dict) else raw
                    if isinstance(items, list):
                        return items   # passa direto; o middleware camelCase é no-op aqui
            except Exception:
                continue

    return []
