"""
API de Gerenciamento de Licitações
Rotas:
  GET    /api/gerenciamento                     — lista gerenciadas do usuário
  POST   /api/gerenciamento                     — adicionar licitação ao gerenciamento
  GET    /api/gerenciamento/{id}                — detalhe
  PATCH  /api/gerenciamento/{id}                — atualizar status / notas / resultado
  DELETE /api/gerenciamento/{id}                — remover do gerenciamento
  GET    /api/gerenciamento/check/{licitacao_id} — verifica se está gerenciada

  GET    /api/gerenciamento/{id}/tarefas        — lista tarefas
  POST   /api/gerenciamento/{id}/tarefas        — criar tarefa
  PATCH  /api/gerenciamento/{id}/tarefas/{tid}  — atualizar tarefa
  DELETE /api/gerenciamento/{id}/tarefas/{tid}  — remover tarefa

  GET    /api/gerenciamento/{id}/anotacoes      — lista anotações
  POST   /api/gerenciamento/{id}/anotacoes      — criar anotação
  PATCH  /api/gerenciamento/{id}/anotacoes/{aid}— atualizar anotação
  DELETE /api/gerenciamento/{id}/anotacoes/{aid}— remover anotação

  GET    /api/gerenciamento/{id}/habilitacao    — lista documentos de habilitação
  POST   /api/gerenciamento/{id}/habilitacao    — criar documento de habilitação
  PATCH  /api/gerenciamento/{id}/habilitacao/{hid} — atualizar documento
  DELETE /api/gerenciamento/{id}/habilitacao/{hid} — remover documento
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import date, datetime as dt, timezone

from ..core.deps import get_current_user
from ..db.session import get_pool


def _parse_date(s: Optional[str]) -> Optional[date]:
    """Converte string ISO (data ou datetime) para date, ou None."""
    if not s:
        return None
    try:
        # Suporta '2026-07-17', '2026-07-17T08:00:00+00:00', etc.
        return dt.fromisoformat(s.replace("Z", "+00:00")).date()
    except Exception:
        try:
            return date.fromisoformat(s[:10])
        except Exception:
            return None


def _parse_date_strict(v: Optional[str]) -> Optional[date]:
    """
    Converte string ISO completa (data ou datetime) para date.
    Levanta ValueError com mensagem clara se o formato não for reconhecido,
    em vez de silenciosamente retornar None.

    Formatos aceitos: '2026-07-17', '2026-07-17T08:00:00', '2026-07-17T08:00:00+00:00',
                      '2026-07-17T08:00:00Z'.
    Strings como '2026-07-17 nonsense' ou '2026-07-17T' são rejeitadas.
    """
    if v is None or v == "":
        return None
    # Parse the full string — no prefix slicing so trailing garbage raises an error.
    try:
        return dt.fromisoformat(v.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        raise ValueError(
            f"Formato de data não reconhecido: '{v}'. "
            "Use ISO 8601 (ex.: '2026-07-17' ou '2026-07-17T08:00:00+00:00')."
        )

router = APIRouter(prefix="/gerenciamento", tags=["gerenciamento"])


# ── Helpers ────────────────────────────────────────────────────────────────

def _iso(v):
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def _ger_row(r: dict) -> dict:
    return {
        "id":                    r["id"],
        "userId":                r["user_id"],
        "licitacaoId":           r["licitacao_id"],
        "licitacaoNumero":       r.get("licitacao_numero"),
        "licitacaoObjeto":       r.get("licitacao_objeto"),
        "licitacaoOrgao":        r.get("licitacao_orgao"),
        "licitacaoCnpj":         r.get("licitacao_cnpj"),
        "licitacaoUf":           r.get("licitacao_uf"),
        "licitacaoMunicipio":    r.get("licitacao_municipio"),
        "licitacaoModalidade":   r.get("licitacao_modalidade"),
        "licitacaoSituacao":     r.get("licitacao_situacao"),
        "licitacaoValor":        r.get("licitacao_valor"),
        "licitacaoDataAbertura": r.get("licitacao_data_abertura"),
        "licitacaoDataEncerramento": r.get("licitacao_data_encerramento"),
        "licitacaoDataPublicacao":   r.get("licitacao_data_publicacao"),
        "licitacaoLinkPncp":     r.get("licitacao_link_pncp"),
        "status":                r["status"],
        "notasGerais":           r.get("notas_gerais"),
        "responsavel":           r.get("responsavel"),
        "resultado":             r.get("resultado"),
        "valorProposta":         float(r["valor_proposta"]) if r.get("valor_proposta") else None,
        "criadoEm":              _iso(r.get("criado_em")),
        "atualizadoEm":          _iso(r.get("atualizado_em")),
        # contadores (injetados por join)
        "totalTarefas":          r.get("total_tarefas", 0),
        "tarefasConcluidas":     r.get("tarefas_concluidas", 0),
        "totalAnotacoes":        r.get("total_anotacoes", 0),
        "docsPendentes":         r.get("docs_pendentes", 0),
    }


def _tarefa_row(r: dict) -> dict:
    return {
        "id":              r["id"],
        "gerenciamentoId": r["gerenciamento_id"],
        "titulo":          r["titulo"],
        "descricao":       r.get("descricao"),
        "prazo":           r["prazo"].isoformat() if r.get("prazo") else None,
        "concluida":       r["concluida"],
        "prioridade":      r["prioridade"],
        "categoria":       r["categoria"],
        "concluidaEm":     _iso(r.get("concluida_em")),
        "criadoEm":        _iso(r.get("criado_em")),
        "atualizadoEm":    _iso(r.get("atualizado_em")),
    }


def _anot_row(r: dict) -> dict:
    return {
        "id":              r["id"],
        "gerenciamentoId": r["gerenciamento_id"],
        "conteudo":        r["conteudo"],
        "criadoEm":        _iso(r.get("criado_em")),
        "atualizadoEm":    _iso(r.get("atualizado_em")),
    }


# ── Schemas ────────────────────────────────────────────────────────────────

class StrictDateMixin(BaseModel):
    """
    Mixin that applies strict ISO-8601 date validation to any date field
    named with the 'Data' convention (e.g. licitacaoDataAbertura, dataEntrega).

    Subclasses that add new Optional[date] fields whose camelCase name
    contains 'Data' automatically receive this validation without any
    additional code.  If a future field uses a different naming pattern,
    add it explicitly to the validator below.
    """

    @field_validator("*", mode="before")
    @classmethod
    def validate_date_fields(cls, v: object, info) -> object:
        # Only intercept fields whose annotation resolves to Optional[date] / date.
        field_name = info.field_name
        field_info = cls.model_fields.get(field_name)
        if field_info is None:
            return v
        # Check annotation for `date` type (handles Optional[date] too).
        annotation = field_info.annotation
        origin = getattr(annotation, "__args__", None)
        # annotation is `date` directly, or Optional[date] (Union[date, None])
        involves_date = annotation is date or (
            origin is not None and date in origin
        )
        if not involves_date:
            return v
        if isinstance(v, date):
            return v
        if isinstance(v, str) or v is None:
            return _parse_date_strict(v)  # type: ignore[arg-type]
        raise ValueError(f"Tipo inválido para campo de data: {type(v).__name__}")


class GerenciamentoCreate(StrictDateMixin):
    licitacaoId: str
    licitacaoNumero: Optional[str] = None
    licitacaoObjeto: Optional[str] = None
    licitacaoOrgao: Optional[str] = None
    licitacaoCnpj: Optional[str] = None
    licitacaoUf: Optional[str] = None
    licitacaoMunicipio: Optional[str] = None
    licitacaoModalidade: Optional[str] = None
    licitacaoSituacao: Optional[str] = None
    licitacaoValor: Optional[str] = None
    licitacaoDataAbertura: Optional[date] = None
    licitacaoDataEncerramento: Optional[date] = None
    licitacaoDataPublicacao: Optional[date] = None
    licitacaoLinkPncp: Optional[str] = None
    responsavel: Optional[str] = None


class GerenciamentoUpdate(StrictDateMixin):
    status: Optional[str] = None
    notasGerais: Optional[str] = None
    responsavel: Optional[str] = None
    resultado: Optional[str] = None
    valorProposta: Optional[float] = None


class TarefaCreate(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    prazo: Optional[date] = None
    prioridade: str = "normal"
    categoria: str = "geral"


class TarefaUpdate(BaseModel):
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    prazo: Optional[date] = None
    concluida: Optional[bool] = None
    prioridade: Optional[str] = None
    categoria: Optional[str] = None


class AnotacaoCreate(BaseModel):
    conteudo: str


class AnotacaoUpdate(BaseModel):
    conteudo: str


HAB_STATUS_VALUES = {"pendente", "enviado", "aprovado", "rejeitado"}

DOCS_DEFAULT = [
    "Certidão de Regularidade do FGTS",
    "Certidão Negativa de Débitos — INSS / Receita Federal",
    "Certidão Negativa de Débitos Trabalhistas (CNDT)",
    "Certidão Negativa de Débitos Municipais",
    "Certidão Negativa de Débitos Estaduais",
    "Balanço Patrimonial",
    "Ato Constitutivo / Contrato Social",
    "Atestado de Capacidade Técnica",
]


class HabilitacaoCreate(BaseModel):
    documento: str
    status: str = "pendente"
    observacoes: Optional[str] = None
    dataEntrega: Optional[date] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in HAB_STATUS_VALUES:
            raise ValueError(f"status deve ser um de: {', '.join(sorted(HAB_STATUS_VALUES))}")
        return v


class HabilitacaoUpdate(BaseModel):
    documento: Optional[str] = None
    status: Optional[str] = None
    observacoes: Optional[str] = None
    dataEntrega: Optional[date] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in HAB_STATUS_VALUES:
            raise ValueError(f"status deve ser um de: {', '.join(sorted(HAB_STATUS_VALUES))}")
        return v


# ── Gerenciamento (CRUD principal) ─────────────────────────────────────────

@router.get("")
async def list_gerenciamento(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT g.*,
               COUNT(t.id)                                         AS total_tarefas,
               COUNT(t.id) FILTER (WHERE t.concluida = TRUE)       AS tarefas_concluidas,
               (SELECT COUNT(*) FROM gerenciamento_anotacoes a
                WHERE a.gerenciamento_id = g.id)                   AS total_anotacoes,
               (SELECT COUNT(*) FROM gerenciamento_habilitacao h
                WHERE h.gerenciamento_id = g.id AND h.status = 'pendente') AS docs_pendentes
          FROM licitacoes_gerenciadas g
          LEFT JOIN gerenciamento_tarefas t ON t.gerenciamento_id = g.id
         WHERE g.user_id = $1
         GROUP BY g.id
         ORDER BY g.criado_em DESC
        """,
        current_user["id"],
    )
    return {"data": [_ger_row(dict(r)) for r in rows], "total": len(rows)}


@router.get("/check/{licitacao_id:path}")
async def check_gerenciamento(licitacao_id: str, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, status FROM licitacoes_gerenciadas WHERE user_id=$1 AND licitacao_id=$2",
        current_user["id"], licitacao_id,
    )
    if row:
        return {"isGerenciada": True, "gerenciamentoId": row["id"], "status": row["status"]}
    return {"isGerenciada": False, "gerenciamentoId": None, "status": None}


@router.post("", status_code=201)
async def add_gerenciamento(body: GerenciamentoCreate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    existing = await pool.fetchrow(
        "SELECT id FROM licitacoes_gerenciadas WHERE user_id=$1 AND licitacao_id=$2",
        current_user["id"], body.licitacaoId,
    )
    if existing:
        raise HTTPException(status_code=409, detail="Licitação já está sendo gerenciada")

    row = await pool.fetchrow(
        """
        INSERT INTO licitacoes_gerenciadas
          (user_id, licitacao_id, licitacao_numero, licitacao_objeto, licitacao_orgao,
           licitacao_cnpj, licitacao_uf, licitacao_municipio, licitacao_modalidade,
           licitacao_situacao, licitacao_valor, licitacao_data_abertura,
           licitacao_data_encerramento, licitacao_data_publicacao, licitacao_link_pncp,
           responsavel)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
        RETURNING *
        """,
        current_user["id"], body.licitacaoId, body.licitacaoNumero, body.licitacaoObjeto,
        body.licitacaoOrgao, body.licitacaoCnpj, body.licitacaoUf, body.licitacaoMunicipio,
        body.licitacaoModalidade, body.licitacaoSituacao, body.licitacaoValor,
        body.licitacaoDataAbertura,
        body.licitacaoDataEncerramento,
        body.licitacaoDataPublicacao,
        body.licitacaoLinkPncp, body.responsavel,
    )
    r = dict(row)
    ger_id = r["id"]

    # Pre-populate default habilitação documents
    await pool.executemany(
        """INSERT INTO gerenciamento_habilitacao
           (gerenciamento_id, user_id, documento, status)
           VALUES ($1, $2, $3, 'pendente')""",
        [(ger_id, current_user["id"], doc) for doc in DOCS_DEFAULT],
    )

    r["total_tarefas"] = 0
    r["tarefas_concluidas"] = 0
    r["total_anotacoes"] = 0
    r["docs_pendentes"] = len(DOCS_DEFAULT)
    return _ger_row(r)


@router.post("/migrar-habilitacao", status_code=200)
async def migrar_habilitacao(current_user: dict = Depends(get_current_user)):
    """
    Insere os documentos padrão (DOCS_DEFAULT) em todas as licitações gerenciadas
    do usuário atual que ainda não possuem nenhum registro em gerenciamento_habilitacao.
    Documentos existentes não são duplicados nem removidos.
    """
    pool = await get_pool()

    # Find gerenciamentos with no habilitacao records at all
    rows = await pool.fetch(
        """
        SELECT g.id, g.user_id
          FROM licitacoes_gerenciadas g
         WHERE g.user_id = $1
           AND NOT EXISTS (
               SELECT 1 FROM gerenciamento_habilitacao h
                WHERE h.gerenciamento_id = g.id
           )
        """,
        current_user["id"],
    )

    migrated = 0
    for row in rows:
        ger_id = row["id"]
        user_id = row["user_id"]
        await pool.executemany(
            """INSERT INTO gerenciamento_habilitacao
               (gerenciamento_id, user_id, documento, status)
               VALUES ($1, $2, $3, 'pendente')""",
            [(ger_id, user_id, doc) for doc in DOCS_DEFAULT],
        )
        migrated += 1

    return {
        "migrated": migrated,
        "docsPerRecord": len(DOCS_DEFAULT),
        "message": (
            f"{migrated} gerenciamento(s) preenchido(s) com {len(DOCS_DEFAULT)} documentos padrão."
            if migrated > 0
            else "Nenhum gerenciamento sem documentos encontrado."
        ),
    }


@router.get("/{ger_id}")
async def get_gerenciamento(ger_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT g.*,
               COUNT(t.id)                                         AS total_tarefas,
               COUNT(t.id) FILTER (WHERE t.concluida = TRUE)       AS tarefas_concluidas,
               (SELECT COUNT(*) FROM gerenciamento_anotacoes a
                WHERE a.gerenciamento_id = g.id)                   AS total_anotacoes
          FROM licitacoes_gerenciadas g
          LEFT JOIN gerenciamento_tarefas t ON t.gerenciamento_id = g.id
         WHERE g.id=$1 AND g.user_id=$2
         GROUP BY g.id
        """,
        ger_id, current_user["id"],
    )
    if not row:
        raise HTTPException(status_code=404, detail="Não encontrado")
    return _ger_row(dict(row))


@router.patch("/{ger_id}")
async def update_gerenciamento(ger_id: int, body: GerenciamentoUpdate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    existing = await pool.fetchrow(
        "SELECT id FROM licitacoes_gerenciadas WHERE id=$1 AND user_id=$2",
        ger_id, current_user["id"],
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Não encontrado")

    sets, vals = [], [ger_id, current_user["id"]]
    n = 3
    for field, col in [("status", "status"), ("notasGerais", "notas_gerais"),
                       ("responsavel", "responsavel"), ("resultado", "resultado"),
                       ("valorProposta", "valor_proposta")]:
        v = getattr(body, field)
        if v is not None:
            sets.append(f"{col}=${n}")
            vals.append(v)
            n += 1

    if not sets:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")

    row = await pool.fetchrow(
        f"UPDATE licitacoes_gerenciadas SET {', '.join(sets)} WHERE id=$1 AND user_id=$2 RETURNING *",
        *vals,
    )
    r = dict(row)
    r["total_tarefas"] = 0
    r["tarefas_concluidas"] = 0
    r["total_anotacoes"] = 0
    return _ger_row(r)


@router.delete("/by-licitacao/{licitacao_id:path}", status_code=204)
async def delete_gerenciamento_by_licitacao(licitacao_id: str, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    result = await pool.execute(
        "DELETE FROM licitacoes_gerenciadas WHERE licitacao_id=$1 AND user_id=$2",
        licitacao_id, current_user["id"],
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Não encontrado")


@router.delete("/{ger_id}", status_code=204)
async def delete_gerenciamento(ger_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    result = await pool.execute(
        "DELETE FROM licitacoes_gerenciadas WHERE id=$1 AND user_id=$2",
        ger_id, current_user["id"],
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Não encontrado")


# ── Tarefas ────────────────────────────────────────────────────────────────

async def _assert_ger(pool, ger_id: int, user_id: str):
    row = await pool.fetchrow(
        "SELECT id FROM licitacoes_gerenciadas WHERE id=$1 AND user_id=$2", ger_id, user_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Gerenciamento não encontrado")


@router.get("/{ger_id}/tarefas")
async def list_tarefas(ger_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    await _assert_ger(pool, ger_id, current_user["id"])
    rows = await pool.fetch(
        "SELECT * FROM gerenciamento_tarefas WHERE gerenciamento_id=$1 ORDER BY prazo NULLS LAST, criado_em",
        ger_id,
    )
    return {"data": [_tarefa_row(dict(r)) for r in rows]}


@router.post("/{ger_id}/tarefas", status_code=201)
async def create_tarefa(ger_id: int, body: TarefaCreate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    await _assert_ger(pool, ger_id, current_user["id"])
    row = await pool.fetchrow(
        """INSERT INTO gerenciamento_tarefas
           (gerenciamento_id, user_id, titulo, descricao, prazo, prioridade, categoria)
           VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *""",
        ger_id, current_user["id"], body.titulo, body.descricao, body.prazo,
        body.prioridade, body.categoria,
    )
    return _tarefa_row(dict(row))


@router.patch("/{ger_id}/tarefas/{tid}")
async def update_tarefa(ger_id: int, tid: int, body: TarefaUpdate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    await _assert_ger(pool, ger_id, current_user["id"])

    sets, vals = [], [tid, ger_id]
    n = 3
    for field, col in [("titulo", "titulo"), ("descricao", "descricao"), ("prazo", "prazo"),
                       ("prioridade", "prioridade"), ("categoria", "categoria")]:
        v = getattr(body, field)
        if v is not None:
            sets.append(f"{col}=${n}")
            vals.append(v)
            n += 1

    if body.concluida is not None:
        sets.append(f"concluida=${n}")
        vals.append(body.concluida)
        n += 1
        if body.concluida:
            sets.append(f"concluida_em=${n}")
            vals.append(dt.now(timezone.utc))
            n += 1
        else:
            sets.append("concluida_em=NULL")

    if not sets:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")

    row = await pool.fetchrow(
        f"UPDATE gerenciamento_tarefas SET {', '.join(sets)} WHERE id=$1 AND gerenciamento_id=$2 RETURNING *",
        *vals,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    return _tarefa_row(dict(row))


@router.delete("/{ger_id}/tarefas/{tid}", status_code=204)
async def delete_tarefa(ger_id: int, tid: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    await _assert_ger(pool, ger_id, current_user["id"])
    result = await pool.execute(
        "DELETE FROM gerenciamento_tarefas WHERE id=$1 AND gerenciamento_id=$2", tid, ger_id
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")


# ── Anotações ──────────────────────────────────────────────────────────────

@router.get("/{ger_id}/anotacoes")
async def list_anotacoes(ger_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    await _assert_ger(pool, ger_id, current_user["id"])
    rows = await pool.fetch(
        "SELECT * FROM gerenciamento_anotacoes WHERE gerenciamento_id=$1 ORDER BY criado_em DESC",
        ger_id,
    )
    return {"data": [_anot_row(dict(r)) for r in rows]}


@router.post("/{ger_id}/anotacoes", status_code=201)
async def create_anotacao(ger_id: int, body: AnotacaoCreate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    await _assert_ger(pool, ger_id, current_user["id"])
    row = await pool.fetchrow(
        "INSERT INTO gerenciamento_anotacoes (gerenciamento_id, user_id, conteudo) VALUES ($1,$2,$3) RETURNING *",
        ger_id, current_user["id"], body.conteudo,
    )
    return _anot_row(dict(row))


@router.patch("/{ger_id}/anotacoes/{aid}")
async def update_anotacao(ger_id: int, aid: int, body: AnotacaoUpdate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    await _assert_ger(pool, ger_id, current_user["id"])
    row = await pool.fetchrow(
        "UPDATE gerenciamento_anotacoes SET conteudo=$3 WHERE id=$1 AND gerenciamento_id=$2 RETURNING *",
        aid, ger_id, body.conteudo,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Anotação não encontrada")
    return _anot_row(dict(row))


@router.delete("/{ger_id}/anotacoes/{aid}", status_code=204)
async def delete_anotacao(ger_id: int, aid: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    await _assert_ger(pool, ger_id, current_user["id"])
    result = await pool.execute(
        "DELETE FROM gerenciamento_anotacoes WHERE id=$1 AND gerenciamento_id=$2", aid, ger_id
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Anotação não encontrada")


# ── Habilitação ────────────────────────────────────────────────────────────

def _hab_row(r: dict) -> dict:
    return {
        "id":              r["id"],
        "gerenciamentoId": r["gerenciamento_id"],
        "documento":       r["documento"],
        "status":          r["status"],
        "observacoes":     r.get("observacoes"),
        "dataEntrega":     r["data_entrega"].isoformat() if r.get("data_entrega") else None,
        "criadoEm":        _iso(r.get("criado_em")),
        "atualizadoEm":    _iso(r.get("atualizado_em")),
    }


@router.get("/{ger_id}/habilitacao")
async def list_habilitacao(ger_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    await _assert_ger(pool, ger_id, current_user["id"])
    rows = await pool.fetch(
        "SELECT * FROM gerenciamento_habilitacao WHERE gerenciamento_id=$1 ORDER BY id",
        ger_id,
    )
    return {"data": [_hab_row(dict(r)) for r in rows]}


@router.post("/{ger_id}/habilitacao", status_code=201)
async def create_habilitacao(ger_id: int, body: HabilitacaoCreate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    await _assert_ger(pool, ger_id, current_user["id"])
    row = await pool.fetchrow(
        """INSERT INTO gerenciamento_habilitacao
           (gerenciamento_id, user_id, documento, status, observacoes, data_entrega)
           VALUES ($1,$2,$3,$4,$5,$6) RETURNING *""",
        ger_id, current_user["id"], body.documento, body.status,
        body.observacoes, body.dataEntrega,
    )
    return _hab_row(dict(row))


@router.patch("/{ger_id}/habilitacao/{hid}")
async def update_habilitacao(ger_id: int, hid: int, body: HabilitacaoUpdate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    await _assert_ger(pool, ger_id, current_user["id"])

    # Use model_fields_set to distinguish omitted fields from explicitly-null ones
    # so that observacoes/dataEntrega can be cleared by sending null.
    sets, vals = [], [hid, ger_id]
    n = 3
    for field, col in [("documento", "documento"), ("status", "status"),
                        ("observacoes", "observacoes"), ("dataEntrega", "data_entrega")]:
        if field not in body.model_fields_set:
            continue  # field was not sent at all — leave DB value unchanged
        sets.append(f"{col}=${n}")
        vals.append(getattr(body, field))
        n += 1

    if not sets:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")

    sets.append(f"atualizado_em=${n}")
    vals.append(dt.now(timezone.utc))

    row = await pool.fetchrow(
        f"UPDATE gerenciamento_habilitacao SET {', '.join(sets)} WHERE id=$1 AND gerenciamento_id=$2 RETURNING *",
        *vals,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    return _hab_row(dict(row))


@router.delete("/{ger_id}/habilitacao/{hid}", status_code=204)
async def delete_habilitacao(ger_id: int, hid: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    await _assert_ger(pool, ger_id, current_user["id"])
    result = await pool.execute(
        "DELETE FROM gerenciamento_habilitacao WHERE id=$1 AND gerenciamento_id=$2", hid, ger_id
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Documento não encontrado")
