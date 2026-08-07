import os
import uuid
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from ..core.deps import get_current_user
from ..db.session import get_pool

router = APIRouter(prefix="/documentos", tags=["documentos"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

GRUPOS_VALIDOS = [
    "Habilitação Jurídica",
    "Regularidade Fiscal, Social e Trabalhista",
    "Qualificação Técnica",
    "Qualificação Econômica Financeira",
    "Outros",
]

SITUACOES_VALIDAS = ["disponivel", "pendente", "coletando"]

MIME_EXTENSIONS = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}


class DocumentoCreate(BaseModel):
    nome: str
    categoria: str = "outro"
    grupo: str = "Outros"
    situacao: str = "pendente"
    tipo_atualizacao: str = "manual"
    data_vencimento: Optional[str] = None
    licitacaoId: Optional[str] = None
    licitacaoObjeto: Optional[str] = None
    url: Optional[str] = None
    tamanho: Optional[int] = None
    tipo: Optional[str] = None
    descricao: Optional[str] = None


class DocumentoUpdate(BaseModel):
    nome: Optional[str] = None
    categoria: Optional[str] = None
    grupo: Optional[str] = None
    situacao: Optional[str] = None
    data_vencimento: Optional[str] = None
    descricao: Optional[str] = None
    url: Optional[str] = None


def _fmt(row) -> dict:
    d = dict(row)
    d["criadoEm"] = d.pop("criado_em").isoformat() if d.get("criado_em") else None
    d["atualizadoEm"] = d.pop("atualizado_em").isoformat() if d.get("atualizado_em") else None
    if d.get("data_vencimento"):
        d["dataVencimento"] = str(d.pop("data_vencimento"))
    else:
        d["dataVencimento"] = None
        d.pop("data_vencimento", None)
    if "tipo_atualizacao" in d:
        d["tipoAtualizacao"] = d.pop("tipo_atualizacao")
    if "licitacao_id" in d:
        d["licitacaoId"] = d.pop("licitacao_id")
    if "licitacao_objeto" in d:
        d["licitacaoObjeto"] = d.pop("licitacao_objeto")
    if "user_id" in d:
        d.pop("user_id")
    return d


@router.get("")
async def list_documentos(
    grupo: Optional[str] = Query(None),
    situacao: Optional[str] = Query(None),
    tipo_atualizacao: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(100),
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    conditions = ["user_id=$1"]
    values: list = [current_user["id"]]
    idx = 2

    if grupo:
        conditions.append(f"grupo=${idx}"); values.append(grupo); idx += 1
    if situacao:
        conditions.append(f"situacao=${idx}"); values.append(situacao); idx += 1
    if tipo_atualizacao:
        conditions.append(f"tipo_atualizacao=${idx}"); values.append(tipo_atualizacao); idx += 1
    if q:
        conditions.append(f"nome ILIKE ${idx}"); values.append(f"%{q}%"); idx += 1

    where = " AND ".join(conditions)
    rows = await pool.fetch(
        f"SELECT * FROM documentos WHERE {where} ORDER BY criado_em DESC LIMIT {limit}",
        *values,
    )
    total = await pool.fetchval(
        f"SELECT COUNT(*) FROM documentos WHERE {where}", *values
    )
    data = [_fmt(dict(r)) for r in rows]
    return {"data": data, "total": int(total or 0)}


@router.post("/upload", status_code=201)
async def upload_documento(
    nome: str = Form(...),
    grupo: str = Form("Outros"),
    situacao: str = Form("disponivel"),
    tipo_atualizacao: str = Form("manual"),
    data_vencimento: Optional[str] = Form(None),
    descricao: Optional[str] = Form(None),
    licitacao_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    # Detect extension
    content_type = file.content_type or "application/octet-stream"
    ext = MIME_EXTENSIONS.get(content_type, os.path.splitext(file.filename or "")[1] or ".bin")

    filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    try:
        with open(filepath, "wb") as f:
            shutil.copyfileobj(file.file, f)
        tamanho = os.path.getsize(filepath)
    finally:
        file.file.close()

    url = f"/api/documentos/file/{filename}"

    pool = await get_pool()
    venc = None
    if data_vencimento:
        try:
            from datetime import date
            venc = date.fromisoformat(data_vencimento)
        except ValueError:
            pass

    row = await pool.fetchrow(
        """INSERT INTO documentos
           (user_id, nome, categoria, grupo, situacao, tipo_atualizacao,
            data_vencimento, licitacao_id, url, tamanho, tipo, descricao)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) RETURNING *""",
        current_user["id"], nome, "outro", grupo, situacao, tipo_atualizacao,
        venc, licitacao_id, url, tamanho, content_type, descricao,
    )
    return _fmt(dict(row))


@router.get("/file/{filename}")
async def serve_file(filename: str, current_user: dict = Depends(get_current_user)):
    """Serve uploaded files (auth-gated)."""
    # Sanitize — no path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nome inválido")
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return FileResponse(filepath)


@router.post("", status_code=201)
async def create_documento(body: DocumentoCreate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    venc = None
    if body.data_vencimento:
        try:
            from datetime import date
            venc = date.fromisoformat(body.data_vencimento)
        except ValueError:
            pass
    row = await pool.fetchrow(
        """INSERT INTO documentos
           (user_id, nome, categoria, grupo, situacao, tipo_atualizacao,
            data_vencimento, licitacao_id, licitacao_objeto, url, tamanho, tipo, descricao)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) RETURNING *""",
        current_user["id"], body.nome, body.categoria, body.grupo,
        body.situacao, body.tipo_atualizacao, venc,
        body.licitacaoId, body.licitacaoObjeto, body.url,
        body.tamanho, body.tipo, body.descricao,
    )
    return _fmt(dict(row))


@router.get("/{doc_id}")
async def get_documento(doc_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM documentos WHERE id=$1 AND user_id=$2", doc_id, current_user["id"]
    )
    if not row:
        raise HTTPException(status_code=404, detail="Não encontrado")
    return _fmt(dict(row))


@router.patch("/{doc_id}")
async def update_documento(doc_id: int, body: DocumentoUpdate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    fields, values, idx = [], [], 1
    mapping = [
        ("nome", "nome"), ("categoria", "categoria"), ("grupo", "grupo"),
        ("situacao", "situacao"), ("descricao", "descricao"), ("url", "url"),
    ]
    for field, col in mapping:
        val = getattr(body, field)
        if val is not None:
            fields.append(f"{col}=${idx}"); values.append(val); idx += 1
    if body.data_vencimento is not None:
        try:
            from datetime import date
            venc = date.fromisoformat(body.data_vencimento) if body.data_vencimento else None
        except ValueError:
            venc = None
        fields.append(f"data_vencimento=${idx}"); values.append(venc); idx += 1

    if not fields:
        row = await pool.fetchrow("SELECT * FROM documentos WHERE id=$1 AND user_id=$2", doc_id, current_user["id"])
        return _fmt(dict(row))

    values.extend([doc_id, current_user["id"]])
    row = await pool.fetchrow(
        f"UPDATE documentos SET {', '.join(fields)}, atualizado_em=NOW() WHERE id=${idx} AND user_id=${idx+1} RETURNING *",
        *values,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Não encontrado")
    return _fmt(dict(row))


@router.delete("/{doc_id}", status_code=204)
async def delete_documento(doc_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    # Also delete the file if stored locally
    row = await pool.fetchrow(
        "SELECT url FROM documentos WHERE id=$1 AND user_id=$2", doc_id, current_user["id"]
    )
    if not row:
        raise HTTPException(status_code=404, detail="Não encontrado")
    url = row["url"] or ""
    if url.startswith("/api/documentos/file/"):
        filename = url.split("/")[-1]
        if "/" not in filename and ".." not in filename:
            filepath = os.path.join(UPLOAD_DIR, filename)
            if os.path.isfile(filepath):
                os.remove(filepath)
    await pool.execute(
        "DELETE FROM documentos WHERE id=$1 AND user_id=$2", doc_id, current_user["id"]
    )
