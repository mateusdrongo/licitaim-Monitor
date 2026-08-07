from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from ..core.deps import get_current_user
from .licitacoes import MOCK_LICITACOES, _normalize

router = APIRouter(prefix="/ai", tags=["ai"])

# ── UF lookup ─────────────────────────────────────────────────────────────────
_UF_SIGLAS = {
    "acre": "AC", "alagoas": "AL", "amapá": "AP", "amazonas": "AM",
    "bahia": "BA", "ceará": "CE", "distrito federal": "DF", "espírito santo": "ES",
    "goiás": "GO", "maranhão": "MA", "minas gerais": "MG", "mato grosso do sul": "MS",
    "mato grosso": "MT", "pará": "PA", "paraíba": "PB", "pernambuco": "PE",
    "piauí": "PI", "paraná": "PR", "rio de janeiro": "RJ", "rio grande do norte": "RN",
    "rondônia": "RO", "roraima": "RR", "rio grande do sul": "RS",
    "santa catarina": "SC", "sergipe": "SE", "são paulo": "SP", "tocantins": "TO",
}
# Adiciona siglas diretamente (ac, al, sp ...)
_UF_SIGLAS.update({sig.lower(): sig for sig in [
    "AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MG","MS","MT",
    "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO",
]})

_MODALIDADE_KW = {
    "pregão eletrônico": ["pregão", "pregao", "eletrônico", "eletronico", "pe"],
    "concorrência": ["concorrência", "concorrencia"],
    "dispensa": ["dispensa"],
    "inexigibilidade": ["inexigibilidade"],
    "credenciamento": ["credenciamento"],
    "leilão": ["leilão", "leilao"],
}

# Palavras-chave → setores que pontuam na busca nos mocks
_SECTOR_KW: dict[str, list[str]] = {
    "ti":          ["ti", "tecnologia", "software", "hardware", "sistema", "computador",
                    "notebook", "laptop", "servidor", "data center", "nuvem", "cloud",
                    "licença", "microsoft", "desenvolvimento", "suporte técnico"],
    "saúde":       ["saúde", "saude", "médico", "medico", "hospital", "medicamento",
                    "farmacêutico", "farmaceutico", "ubs", "laboratorial", "diagnóstico",
                    "equipamento hospitalar", "insumo", "oncológico"],
    "construção":  ["construção", "construcao", "obra", "pavimentação", "pavimentacao",
                    "rodovia", "infraestrutura", "engenharia", "reforma", "edificação"],
    "educação":    ["educação", "educacao", "escola", "universidade", "tablet", "material escolar",
                    "merenda", "didático"],
    "limpeza":     ["limpeza", "higienização", "higienizacao", "facilities", "conservação",
                    "conservacao", "zeladoria"],
    "segurança":   ["segurança", "seguranca", "vigilância", "vigilancia", "patrimonial",
                    "armada", "eletrônica"],
    "transporte":  ["transporte", "veículo", "veiculo", "caminhão", "caminhao", "ônibus",
                    "onibus", "logística", "logistica"],
    "mobiliário":  ["mobiliário", "mobiliario", "cadeira", "mesa", "mobília", "mobilia",
                    "escritório", "ergonômico"],
    "laboratório": ["laboratório", "laboratorio", "reagente", "pesquisa", "científico",
                    "cientifico", "quimico"],
    "petróleo":    ["petróleo", "petroleo", "petrobras", "plataforma", "manutenção industrial"],
}


def _parse_query(q: str) -> dict:
    """Extrai filtros de uma query em linguagem natural."""
    ql = q.lower()

    # UFs
    ufs_found = []
    for nome, sig in _UF_SIGLAS.items():
        # palavras completas / siglas curtas
        if f" {nome} " in f" {ql} " or f"({nome})" in ql or f"estado de {nome}" in ql:
            if sig not in ufs_found:
                ufs_found.append(sig)

    # Modalidades
    modalidades_found = []
    for modal, kws in _MODALIDADE_KW.items():
        if any(kw in ql for kw in kws):
            modalidades_found.append(modal)

    # Valor mínimo
    valor_min = None
    import re
    # "acima de X milhão/mil", "mínimo de X", "> R$ X"
    for pattern, mult in [
        (r"(\d+(?:[.,]\d+)?)\s*(?:milhões?|milhao|milhão|mi\b)", 1_000_000),
        (r"(\d+(?:[.,]\d+)?)\s*mil\b", 1_000),
        (r"r\$\s*(\d+(?:[.,]\d+)?)", 1),
    ]:
        m = re.search(pattern, ql)
        if m:
            try:
                num = float(m.group(1).replace(".", "").replace(",", "."))
                val = num * mult
                if valor_min is None or val < valor_min:
                    valor_min = val
            except ValueError:
                pass

    # Palavras-chave extraídas
    stop = {"de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas",
             "e", "ou", "com", "para", "que", "uma", "um", "por"}
    palavras = [w for w in ql.split() if len(w) > 3 and w not in stop]

    return {
        "palavras_chave": palavras[:8],
        "modalidades":    modalidades_found,
        "ufs":            ufs_found,
        "valor_min":      valor_min,
        "valor_max":      None,
    }


def _score_result(lic: dict, q_lower: str, filtros: dict) -> int:
    """Pontua um resultado normalizado de mock. Score > 0 = relevante."""
    obj = lic["objeto"].lower()
    org = lic.get("orgao_nome", "").lower()
    text = obj + " " + org
    score = 0

    # Filtro por UF
    if filtros["ufs"] and lic["uf"] not in [u.upper() for u in filtros["ufs"]]:
        return -1  # exclui se UF não bate

    # Filtro por modalidade
    if filtros["modalidades"]:
        lic_modal = lic.get("modalidade", "").lower()
        if not any(m.lower() in lic_modal for m in filtros["modalidades"]):
            score -= 2  # penaliza mas não exclui (pode ter match por texto)

    # Filtro por valor
    val = lic.get("valor_estimado")
    if filtros["valor_min"] and val:
        if float(val) < filtros["valor_min"]:
            return -1   # exclui se abaixo do mínimo

    # Score por palavras individuais da query no texto
    for palavra in q_lower.split():
        if len(palavra) < 3:
            continue
        if palavra in text:
            score += 4

    # Score por palavras-chave extraídas
    for palavra in filtros["palavras_chave"]:
        if palavra in text:
            score += 2

    # Score por setor
    for setor, kws in _SECTOR_KW.items():
        setor_match_query = any(kw in q_lower for kw in kws)
        setor_match_doc   = any(kw in text for kw in kws)
        if setor_match_query and setor_match_doc:
            score += 5

    return score


class SearchRequest(BaseModel):
    query: str
    contexto: Optional[str] = None


@router.post("/search")
async def ai_search(body: SearchRequest, current_user: dict = Depends(get_current_user)):
    q    = body.query.strip()
    ql   = q.lower()

    filtros = _parse_query(ql)

    # Pontua todos os mocks
    all_normalized = [_normalize(m) for m in MOCK_LICITACOES]
    scored = []
    for lic in all_normalized:
        s = _score_result(lic, ql, filtros)
        if s >= 0:
            scored.append((s, lic))

    scored.sort(key=lambda x: -x[0])

    # Resultados positivos; se nenhum, retorna os 3 mais relevantes sem filtro de exclusão
    positives = [(s, r) for s, r in scored if s > 0]
    if positives:
        resultados = [r for _, r in positives[:10]]
    else:
        # Sem relevância detectada — retorna amostra variada
        resultados = [r for _, r in scored[:5]]

    # Monta interpretação legível
    partes_interp = [f"Busca semântica por: «{q}»."]
    if filtros["ufs"]:
        partes_interp.append(f"Estado(s) detectado(s): {', '.join(filtros['ufs'])}.")
    if filtros["modalidades"]:
        partes_interp.append(f"Modalidade(s): {', '.join(filtros['modalidades'])}.")
    if filtros["valor_min"]:
        valor_fmt = f"R$ {filtros['valor_min']:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
        partes_interp.append(f"Valor mínimo estimado: {valor_fmt}.")
    if filtros["palavras_chave"]:
        partes_interp.append(f"Termos-chave identificados: {', '.join(filtros['palavras_chave'][:5])}.")
    partes_interp.append(f"{len(resultados)} resultado(s) encontrado(s) no índice.")
    interpretacao = " ".join(partes_interp)

    return {
        "query":         q,
        "interpretacao": interpretacao,
        "filtros_gerados": {
            "palavras_chave": filtros["palavras_chave"],
            "modalidades":    filtros["modalidades"],
            "ufs":            filtros["ufs"],
            "valor_min":      filtros["valor_min"],
            "valor_max":      filtros["valor_max"],
        },
        "resultados":        resultados,
        "total_encontrados": len(resultados),
    }


@router.get("/sugestoes")
async def sugestoes(current_user: dict = Depends(get_current_user)):
    results = [_normalize(m) for m in MOCK_LICITACOES[:3]]
    return {
        "sugestoes": results,
        "criterio":  "Baseado nos seus monitoramentos e histórico de participação",
    }
