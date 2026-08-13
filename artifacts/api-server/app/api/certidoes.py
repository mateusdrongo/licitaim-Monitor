import os
import uuid
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from datetime import date
from ..core.deps import get_current_user
from ..db.session import get_pool

router = APIRouter(prefix="/certidoes", tags=["certidoes"])

# Compartilha o mesmo diretório de uploads dos documentos
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Allowlist estrita: apenas MIME types conhecidos e seguros para certidões.
# A extensão é SEMPRE derivada do MIME type declarado pelo servidor — nunca
# do nome de arquivo ou extensão enviados pelo cliente.
MIME_EXTENSIONS: dict[str, str] = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}


class CertidaoCreate(BaseModel):
    nome: str
    tipo: str = "outro"
    orgaoEmissor: Optional[str] = None
    numero: Optional[str] = None
    dataEmissao: Optional[date] = None
    dataVencimento: Optional[date] = None
    descricao: Optional[str] = None


class CertidaoUpdate(BaseModel):
    nome: Optional[str] = None
    tipo: Optional[str] = None
    orgaoEmissor: Optional[str] = None
    numero: Optional[str] = None
    dataEmissao: Optional[date] = None
    dataVencimento: Optional[date] = None
    descricao: Optional[str] = None


def _status(data_venc: Optional[date]) -> str:
    if not data_venc:
        return "sem_prazo"
    today = date.today()
    if data_venc < today:
        return "vencida"
    if (data_venc - today).days <= 30:
        return "a_vencer"
    return "ativa"


def _fmt(row) -> dict:
    d = dict(row)
    d["criadoEm"] = d.pop("criado_em").isoformat() if d.get("criado_em") else None
    d["atualizadoEm"] = d.pop("atualizado_em").isoformat() if d.get("atualizado_em") else None
    d["dataEmissao"] = d.pop("data_emissao").isoformat() if d.get("data_emissao") else None
    d["dataVencimento"] = d.pop("data_vencimento").isoformat() if d.get("data_vencimento") else None
    d["status"] = _status(
        date.fromisoformat(d["dataVencimento"]) if d.get("dataVencimento") else None
    )
    # Normaliza arquivo_url → arquivoUrl para o frontend
    d["arquivoUrl"] = d.pop("arquivo_url", None)
    return d


# ── Listar ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_certidoes(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM certidoes WHERE user_id=$1 ORDER BY data_vencimento ASC NULLS LAST",
        current_user["id"],
    )
    return [_fmt(dict(r)) for r in rows]


# ── Upload com arquivo ──────────────────────────────────────────────────────

@router.post("/upload", status_code=201)
async def upload_certidao(
    nome: str = Form(...),
    tipo: str = Form("outro"),
    orgaoEmissor: Optional[str] = Form(None),
    numero: Optional[str] = Form(None),
    dataEmissao: Optional[str] = Form(None),
    dataVencimento: Optional[str] = Form(None),
    descricao: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Cria uma certidão com arquivo anexo (multipart/form-data)."""
    content_type = file.content_type or ""
    ext = MIME_EXTENSIONS.get(content_type)
    if ext is None:
        raise HTTPException(
            status_code=415,
            detail=(
                "Tipo de arquivo não permitido. "
                "Formatos aceitos: PDF, PNG, JPEG, DOC, DOCX, XLS, XLSX."
            ),
        )

    filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    try:
        with open(filepath, "wb") as f:
            shutil.copyfileobj(file.file, f)
    finally:
        file.file.close()

    arquivo_url = f"/api/certidoes/file/{filename}"

    pool = await get_pool()
    emissao = _parse_date(dataEmissao)
    vencimento = _parse_date(dataVencimento)

    row = await pool.fetchrow(
        """INSERT INTO certidoes
           (user_id, nome, tipo, orgao_emissor, numero, data_emissao, data_vencimento,
            descricao, arquivo_url)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING *""",
        current_user["id"], nome, tipo, orgaoEmissor or None,
        numero or None, emissao, vencimento, descricao or None, arquivo_url,
    )
    return _fmt(dict(row))


# ── Servir arquivo (autenticado + autorizado) ───────────────────────────────

@router.get("/file/{filename}")
async def serve_certidao_file(
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Serve o arquivo de uma certidão.

    Segurança:
    - Verifica que o arquivo pertence a uma certidão do usuário autenticado
      (consulta certidoes WHERE arquivo_url LIKE %filename AND user_id = current_user).
    - Serve com Content-Disposition: attachment para evitar execução inline de
      conteúdo ativo no navegador.
    - Rejeita nomes com traversal (/, \\, ..).
    """
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nome inválido")

    # Autorização: o arquivo deve pertencer a uma certidão do usuário
    pool = await get_pool()
    cert_row = await pool.fetchrow(
        "SELECT id FROM certidoes WHERE arquivo_url = $1 AND user_id = $2",
        f"/api/certidoes/file/{filename}",
        current_user["id"],
    )
    if cert_row is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    return FileResponse(
        filepath,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Criar sem arquivo (JSON) ────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_certidao(body: CertidaoCreate, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    row = await pool.fetchrow(
        """INSERT INTO certidoes
           (user_id, nome, tipo, orgao_emissor, numero, data_emissao, data_vencimento, descricao)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *""",
        current_user["id"], body.nome, body.tipo, body.orgaoEmissor,
        body.numero, body.dataEmissao, body.dataVencimento, body.descricao,
    )
    return _fmt(dict(row))


# ── Atualizar ───────────────────────────────────────────────────────────────

@router.patch("/{cert_id}")
async def update_certidao(
    cert_id: int,
    body: CertidaoUpdate,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    col_map = [
        ("nome", "nome"), ("tipo", "tipo"), ("orgaoEmissor", "orgao_emissor"),
        ("numero", "numero"), ("dataEmissao", "data_emissao"),
        ("dataVencimento", "data_vencimento"), ("descricao", "descricao"),
    ]
    fields, values, idx = [], [], 1
    for attr, col in col_map:
        val = getattr(body, attr)
        if val is not None:
            fields.append(f"{col}=${idx}"); values.append(val); idx += 1
    if not fields:
        row = await pool.fetchrow(
            "SELECT * FROM certidoes WHERE id=$1 AND user_id=$2", cert_id, current_user["id"]
        )
        if not row:
            raise HTTPException(status_code=404, detail="Não encontrado")
        return _fmt(dict(row))
    values.extend([cert_id, current_user["id"]])
    row = await pool.fetchrow(
        f"UPDATE certidoes SET {', '.join(fields)} WHERE id=${idx} AND user_id=${idx+1} RETURNING *",
        *values,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Não encontrado")
    return _fmt(dict(row))


# ── Remover ─────────────────────────────────────────────────────────────────

@router.delete("/{cert_id}", status_code=204)
async def delete_certidao(cert_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT arquivo_url FROM certidoes WHERE id=$1 AND user_id=$2",
        cert_id, current_user["id"],
    )
    if not row:
        raise HTTPException(status_code=404, detail="Não encontrado")
    # Remove o arquivo em disco se existir
    url = row["arquivo_url"] or ""
    if url.startswith("/api/certidoes/file/"):
        fname = url.split("/")[-1]
        if "/" not in fname and ".." not in fname:
            fpath = os.path.join(UPLOAD_DIR, fname)
            if os.path.isfile(fpath):
                os.remove(fpath)
    await pool.execute(
        "DELETE FROM certidoes WHERE id=$1 AND user_id=$2", cert_id, current_user["id"]
    )


# ── Helpers ─────────────────────────────────────────────────────────────────

def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        return None
