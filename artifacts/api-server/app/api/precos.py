from fastapi import APIRouter, Depends, Query
from typing import Optional
from ..core.deps import get_current_user

router = APIRouter(prefix="/precos", tags=["precos"])

# Dados mock de histórico de preços baseados nos dados de licitação
HISTORICO_MOCK = [
    {"descricao": "Notebook Dell Inspiron 15", "uf": "SP", "orgao": "Prefeitura de São Paulo", "valor": 3200.0, "quantidade": 50, "data": "2024-03-15", "modalidade": "Pregão Eletrônico"},
    {"descricao": "Notebook Dell Inspiron 15", "uf": "RJ", "orgao": "Estado do Rio de Janeiro", "valor": 3050.0, "quantidade": 100, "data": "2024-05-20", "modalidade": "Pregão Eletrônico"},
    {"descricao": "Notebook Dell Inspiron 15", "uf": "MG", "orgao": "UFMG", "valor": 2980.0, "quantidade": 80, "data": "2024-07-10", "modalidade": "Pregão Eletrônico"},
    {"descricao": "Notebook Dell Inspiron 15", "uf": "CE", "orgao": "UFC", "valor": 3100.0, "quantidade": 60, "data": "2024-09-05", "modalidade": "Pregão Eletrônico"},
    {"descricao": "Cadeira Ergonômica", "uf": "SP", "orgao": "Ministério da Fazenda", "valor": 850.0, "quantidade": 200, "data": "2024-02-28", "modalidade": "Pregão Eletrônico"},
    {"descricao": "Cadeira Ergonômica", "uf": "DF", "orgao": "TCU", "valor": 920.0, "quantidade": 150, "data": "2024-06-15", "modalidade": "Pregão Eletrônico"},
    {"descricao": "Reagentes Laboratoriais", "uf": "CE", "orgao": "UFC", "valor": 450.0, "quantidade": 500, "data": "2024-08-20", "modalidade": "Pregão Eletrônico"},
    {"descricao": "Reagentes Laboratoriais", "uf": "SP", "orgao": "USP", "valor": 480.0, "quantidade": 300, "data": "2024-10-01", "modalidade": "Pregão Eletrônico"},
]


@router.get("/historico")
async def historico_precos(
    q: Optional[str] = Query(None),
    uf: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    results = HISTORICO_MOCK
    if q:
        ql = q.lower()
        results = [r for r in results if ql in r["descricao"].lower()]
    if uf:
        results = [r for r in results if r["uf"].upper() == uf.upper()]
    return {"data": results, "total": len(results)}
